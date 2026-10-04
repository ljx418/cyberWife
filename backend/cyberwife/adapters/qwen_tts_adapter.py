"""QwenTtsAdapter — V1 不换底座情况下接入 Qwen3-TTS。

按教程与 M3-stretch 决策：在 V1 现有 backend/cyberwife 架构上接入 Qwen3-TTS 12Hz-1.7B-Base，
不引入 huggingface/speech-to-speech 框架。

按 qwen_tts 0.0.2 + transformers 4.57 实际行为（Q2 C monkey-patch 路径）：
- Qwen3TTSModel.from_pretrained 内部传 dtype="bf16"（str），在 transformers 4.57 中报错。
- 解法：调用前 monkey-patch transformers.AutoModel.from_pretrained 把字符串 dtype 替换为 torch.bfloat16。

按 ports.tts.TtsPort 接口（FR-05 voice clone + 流式 PCM Int16 LE 16kHz）。
按 implementation-contracts §6 TTS 端点：POST /api/v1/assets/{kind}/preview 已支持上传参考音频。
"""
from __future__ import annotations

import os
import time
import threading
from typing import Iterator, Optional

import numpy as np
import torch

from cyberwife.infrastructure.structured_logger import StructuredLogger
from cyberwife.ports.tts import TtsPort


def _monkeypatch_transformers_dtype():
    """Q2 C 路径：transformers 4.57 + qwen_tts 0.0.2 + dtype=str 报错。

    在 qwen3_tts_model.from_pretrained 调用前替换 dtype 字符串为 torch.dtype。
    此 monkey-patch 只在 Qwen3-TTS 加载期间生效；其他模型加载不受影响。
    """
    import transformers

    _orig = transformers.AutoModel.from_pretrained

    def _patched(*args, **kwargs):
        dtype = kwargs.get("dtype")
        if isinstance(dtype, str):
            mapping = {
                "bf16": torch.bfloat16,
                "fp16": torch.float16,
                "fp32": torch.float32,
                "float16": torch.float16,
                "float32": torch.float32,
                "bfloat16": torch.bfloat16,
            }
            if dtype in mapping:
                kwargs["dtype"] = mapping[dtype]
        return _orig(*args, **kwargs)

    # 在类层级覆盖（AutoModel 是 class，不是实例）
    setattr(transformers.AutoModel, "from_pretrained", _patched)


class QwenTtsAdapter(TtsPort):
    """Qwen3-TTS 12Hz-1.7B-Base 适配器（qwen_tts 0.0.2 + transformers 4.57 monkey-patch）。"""

    _model = None
    _lock = threading.Lock()
    _cached_prompt = None  # type: ignore
    _cached_prompt_key = None  # tuple (ref_audio, ref_text)

    def __init__(
        self,
        model_dir: str,
        *,
        device: str = "cuda",
        dtype: str = "bf16",
        default_ref_audio: Optional[str] = None,
        default_ref_text: str = "",
    ) -> None:
        self._model_dir = model_dir
        self._device = device
        self._dtype = dtype
        self._default_ref_audio = default_ref_audio
        self._default_ref_text = default_ref_text
        self._logger = StructuredLogger(name="cyberwife.tts")
        self._inflight: dict[str, threading.Event] = {}
        self._cancel_event = threading.Event()
        self.last_metrics: dict[str, float | int | str] = {}

    def _ensure_loaded(self) -> None:
        if QwenTtsAdapter._model is not None:
            return
        with QwenTtsAdapter._lock:
            if QwenTtsAdapter._model is not None:
                return
            _monkeypatch_transformers_dtype()
            t0 = time.time()
            from qwen_tts import Qwen3TTSModel  # type: ignore

            QwenTtsAdapter._model = Qwen3TTSModel.from_pretrained(
                self._model_dir,
                device_map=self._device if self._device != "cpu" else "cpu",
                dtype=self._dtype,
            )
            load_ms = int((time.time() - t0) * 1000)
            self._logger.emit(
                "tts.load",
                "tts",
                duration_ms=load_ms,
                device=self._device,
                dtype=self._dtype,
            )

    def health(self) -> dict:
        return {
            "status": "ready" if QwenTtsAdapter._model is not None else "loading",
            "device": self._device,
            "dtype": self._dtype,
            "model_dir": self._model_dir,
        }

    def synthesize_stream(
        self,
        text: str,
        reference_audio_path: str,
        reference_transcript: str,
        max_duration_s: float = 60.0,
    ) -> Iterator[bytes]:
        """流式 yield 16kHz 单声道 PCM Int16 LE 帧（每帧 640 字节 = 20ms）。

        Q3R-rerun2 改进：默认 non_streaming_mode=True（qwen_tts 0.0.2 注释确认默认 False
        是"模拟流式"，会插入间隔静音导致断句；non_streaming_mode=True 强制单段生成）。
        """
        if not reference_audio_path:
            reference_audio_path = self._default_ref_audio or ""
        if not reference_audio_path:
            raise ValueError("reference_audio_path required for voice clone")
        self._ensure_loaded()
        if QwenTtsAdapter._model is None:
            raise RuntimeError("Qwen3-TTS model not loaded")
        ref_text = reference_transcript or self._default_ref_text
        t0 = time.perf_counter()
        self._cancel_event.clear()
        try:
            prompt_key = (os.path.abspath(reference_audio_path), ref_text)
            generate_args = {
                "text": text,
                "non_streaming_mode": True,
                "max_duration_s": max_duration_s,
            }
            if hasattr(QwenTtsAdapter._model, "create_voice_clone_prompt"):
                if QwenTtsAdapter._cached_prompt_key != prompt_key:
                    QwenTtsAdapter._cached_prompt = QwenTtsAdapter._model.create_voice_clone_prompt(
                        ref_audio=reference_audio_path,
                        ref_text=ref_text,
                    )
                    QwenTtsAdapter._cached_prompt_key = prompt_key
                generate_args["voice_clone_prompt"] = QwenTtsAdapter._cached_prompt
            else:  # minimal test doubles and older qwen-tts releases
                generate_args.update(ref_audio=reference_audio_path, ref_text=ref_text)
            wavs, sr = QwenTtsAdapter._model.generate_voice_clone(**generate_args)
        except Exception as e:
            self._logger.emit(
                "tts.error",
                "tts",
                error_code="tts.synthesis_failed",
                message=str(e)[:200],
            )
            raise
        # wavs 是 List[np.ndarray] (24kHz)；重采样到 16kHz mono
        first_packet_ms = None
        output_bytes = 0
        for wav in wavs:
            try:
                audio_16k = _resample_to_16k_mono_int16(wav, sr)
            except Exception:
                audio_16k = _to_int16_mono(wav)
            # 按 20ms 切帧，每帧 640 字节（16000 * 0.02 * 2 bytes = 640）
            frame_samples = 320
            for i in range(0, len(audio_16k) - frame_samples + 1, frame_samples):
                if self._cancel_event.is_set():
                    break
                if first_packet_ms is None:
                    first_packet_ms = (time.perf_counter() - t0) * 1000
                frame = audio_16k[i:i + frame_samples].tobytes()
                output_bytes += len(frame)
                yield frame
            # 剩余不足一帧的部分作为最后一帧
            rem = len(audio_16k) % frame_samples
            if rem > 0:
                pad = np.zeros(frame_samples - rem, dtype=np.int16)
                last = np.concatenate([audio_16k[-(rem):], pad])
                if not self._cancel_event.is_set():
                    if first_packet_ms is None:
                        first_packet_ms = (time.perf_counter() - t0) * 1000
                    frame = last.tobytes()
                    output_bytes += len(frame)
                    yield frame
        wall_s = time.perf_counter() - t0
        audio_s = output_bytes / 32000
        duration_ms = int(wall_s * 1000)
        self.last_metrics = {
            "first_packet_ms": round(first_packet_ms or wall_s * 1000, 1),
            "wall_ms": round(wall_s * 1000, 1),
            "audio_s": round(audio_s, 3),
            "rtf": round(wall_s / audio_s, 4) if audio_s else 0.0,
            "cancelled": int(self._cancel_event.is_set()),
        }
        self._logger.emit(
            "tts.synthesize",
            "tts",
            duration_ms=duration_ms,
            text_length=len(text),
        )

    def cancel(self, request_id: str) -> bool:
        del request_id
        self._cancel_event.set()
        return True


def _to_int16_mono(wav: np.ndarray) -> np.ndarray:
    """任意 dtype → int16 mono numpy。"""
    if wav.ndim > 1:
        wav = wav.mean(axis=-1)
    if wav.dtype == np.int16:
        return wav
    wav = wav.astype(np.float32)
    if wav.max() > 1.0 or wav.min() < -1.0:
        wav = wav / max(abs(wav.max()), abs(wav.min()))
    wav = wav * 32767.0
    return wav.astype(np.int16)


def _resample_to_16k_mono_int16(wav: np.ndarray, src_sr: int) -> np.ndarray:
    """线性重采样到 16kHz mono int16。"""
    if wav.ndim > 1:
        wav = wav.mean(axis=-1)
    if wav.dtype != np.float32:
        wav = wav.astype(np.float32)
    if src_sr == 16000:
        return _to_int16_mono(wav)
    # 简单线性重采样（M3 阶段；M5 可换 scipy.signal.resample_poly）
    n_in = len(wav)
    n_out = int(n_in * 16000 / src_sr)
    if n_out <= 0:
        return np.zeros(0, dtype=np.int16)
    xp = np.arange(n_in)
    xq = np.linspace(0, n_in - 1, n_out)
    resampled = np.interp(xq, xp, wav).astype(np.float32)
    return _to_int16_mono(resampled)
