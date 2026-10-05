"""FasterWhisperAdapter — M3-02 ASR 适配器（实现 ports.asr.AsrPort）。

按 model-manifest §1 ASR 行（Faster-Whisper large-v3-turbo）。
按 implementation-contracts §18 ASR deadline。

M3 阶段：CPU FP16 (int8) 推理；GPU 在 M3-07 实测后切换。
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

from cyberwife.ports.asr import AsrPort, AsrResult, AsrSegment
from cyberwife.infrastructure.structured_logger import StructuredLogger


MANDARIN_SIMPLIFIED_PROMPT = "以下是普通话简体中文对话"


class FasterWhisperAdapter(AsrPort):
    """Faster-Whisper CTranslate2 适配器。"""

    def __init__(
        self,
        model_dir: str,
        *,
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        from opencc import OpenCC

        self._model_dir = model_dir
        self._device = device
        self._compute_type = compute_type
        self._simplifier = OpenCC("t2s")
        self._model = None
        self._logger = StructuredLogger(name="cyberwife.asr")
        self._load()

    def _load(self) -> None:
        t0 = time.time()
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self._model_dir,
            device=self._device,
            compute_type=self._compute_type,
        )
        load_ms = int((time.time() - t0) * 1000)
        self._logger.emit(
            "asr.load",
            "asr",
            duration_ms=load_ms,
            device=self._device,
            compute_type=self._compute_type,
        )

    def transcribe(self, audio_pcm: bytes, sample_rate: int = 16000) -> AsrResult:
        if self._model is None:
            self._load()
        # 字节 → float32 [-1, 1]
        if sample_rate != 16000:
            raise ValueError(f"only 16000Hz supported, got {sample_rate}")
        if not audio_pcm or len(audio_pcm) % 2:
            raise ValueError("audio_pcm must contain non-empty PCM16 samples")
        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        t0 = time.time()
        segs, info = self._model.transcribe(
            audio,
            language="zh",
            task="transcribe",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=MANDARIN_SIMPLIFIED_PROMPT,
        )
        segs = list(segs)
        duration_ms = int((time.time() - t0) * 1000)
        text = self._simplifier.convert("".join(s.text for s in segs)).strip()
        # confidence 取所有 segment 的 avg_probability 均值
        probs = [getattr(s, "avg_logprob", 0.0) for s in segs if getattr(s, "avg_logprob", None) is not None]
        if probs:
            confidence = float(np.exp(np.mean(probs)))
        else:
            confidence = 0.0
        self._logger.emit(
            "asr.transcribe",
            "asr",
            duration_ms=duration_ms,
            text_segments=len(segs),
        )
        segments = tuple(
            AsrSegment(
                start_ms=max(0, round(float(s.start) * 1000)),
                end_ms=max(0, round(float(s.end) * 1000)),
                text=self._simplifier.convert(s.text).strip(),
                confidence=float(np.exp(getattr(s, "avg_logprob", 0.0))),
            )
            for s in segs
            if s.text.strip()
        )
        return AsrResult(
            text=text,
            confidence=confidence,
            language="zh",
            is_partial=False,
            segments=segments,
        )

    def health(self) -> dict:
        return {
            "status": "ready" if self._model is not None else "loading",
            "device": self._device,
            "compute_type": self._compute_type,
            "model_dir": self._model_dir,
        }
