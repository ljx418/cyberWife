"""CosyVoice2 zero-shot voice-clone adapter.

The upstream CosyVoice repository is kept outside this source tree because it
has its own pinned runtime.  This adapter only depends on its public
``CosyVoice2`` and ``load_wav`` entry points and preserves the application's
16 kHz, mono, signed-16-bit, 20 ms frame contract.
"""
from __future__ import annotations

import sys
import threading
import time
import os
import hashlib
import json
import gc
from collections.abc import Iterator
from pathlib import Path
from typing import Callable

import numpy as np

from cyberwife.infrastructure.structured_logger import StructuredLogger
from cyberwife.ports.tts import TtsPort


FRAME_BYTES = 640  # 20 ms * 16 kHz * int16


class CosyVoiceTensorRtProfile:
    """Fail-closed identity check for a GPU-specific derived TensorRT engine."""

    ENGINE_NAME = "flow.decoder.estimator.fp16.mygpu.plan"
    ONNX_NAME = "flow.decoder.estimator.fp32.onnx"
    MANIFEST_NAME = "flow.decoder.estimator.fp16.mygpu.manifest.json"

    def __init__(
        self,
        model_dir: Path,
        *,
        model_revision: str,
        source_revision: str,
        runtime_identity: Callable[[], dict[str, str]] | None = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.model_revision = model_revision
        self.source_revision = source_revision
        self.engine_path = self.model_dir / self.ENGINE_NAME
        self.onnx_path = self.model_dir / self.ONNX_NAME
        self.manifest_path = self.model_dir / self.MANIFEST_NAME
        self._runtime_identity = runtime_identity or self._detect_runtime_identity

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _detect_runtime_identity() -> dict[str, str]:
        import tensorrt as trt
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("TensorRT requires a CUDA device")
        return {
            "tensorrt_version": str(trt.__version__),
            "gpu_name": str(torch.cuda.get_device_name(0)),
        }

    def _expected(self) -> dict[str, str | int]:
        identity = self._runtime_identity()
        return {
            "schema_version": 1,
            "precision": "fp16",
            "model_revision": self.model_revision,
            "source_revision": self.source_revision,
            "onnx_sha256": self._sha256(self.onnx_path),
            "tensorrt_version": identity["tensorrt_version"],
            "gpu_name": identity["gpu_name"],
        }

    def validate(self) -> dict[str, str]:
        if not self.onnx_path.is_file() or not self.engine_path.is_file() or not self.manifest_path.is_file():
            return {"status": "missing", "reason": "engine_or_manifest_missing"}
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            expected = self._expected()
            for key, value in expected.items():
                if manifest.get(key) != value:
                    return {"status": "invalid", "reason": "manifest_mismatch"}
            if manifest.get("engine_sha256") != self._sha256(self.engine_path):
                return {"status": "invalid", "reason": "engine_hash_mismatch"}
        except Exception:
            return {"status": "invalid", "reason": "manifest_unreadable"}
        return {"status": "ready", "reason": "validated"}

    def record_built_engine(self) -> None:
        if not self.engine_path.is_file() or not self.onnx_path.is_file():
            raise FileNotFoundError("TensorRT build did not produce the required engine")
        manifest = self._expected()
        manifest["engine_sha256"] = self._sha256(self.engine_path)
        manifest["engine_size_bytes"] = self.engine_path.stat().st_size
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.manifest_path)


class CosyVoiceTtsAdapter(TtsPort):
    """CosyVoice2-0.5B streaming adapter for one local GPU worker."""

    _model = None
    _model_key: tuple[str, bool] | None = None
    _load_lock = threading.Lock()
    _speaker_cache_lock = threading.Lock()

    def __init__(
        self,
        model_dir: str,
        *,
        source_dir: str,
        fp16: bool = True,
        stream: bool = True,
        load_jit: bool = False,
        load_trt: bool = False,
        allow_trt_build: bool = False,
        model_revision: str = "eec1ae6c79877dbd9379285cf8789c9e0879293d",
        source_revision: str = "074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc",
    ) -> None:
        self._model_dir = Path(model_dir).expanduser().resolve()
        self._source_dir = Path(source_dir).expanduser().resolve()
        self._fp16 = fp16
        self._stream = stream
        self._load_jit = load_jit
        self._load_trt = load_trt
        self._allow_trt_build = allow_trt_build
        self._trt_profile = CosyVoiceTensorRtProfile(
            self._model_dir,
            model_revision=model_revision,
            source_revision=source_revision,
        )
        self._logger = StructuredLogger(name="cyberwife.tts.cosyvoice")
        self._cancel_event = threading.Event()
        self.last_metrics: dict[str, float | int | str] = {}

    def _ensure_loaded(self) -> None:
        model_key = (str(self._model_dir), self._load_trt)
        if CosyVoiceTtsAdapter._model is not None:
            if CosyVoiceTtsAdapter._model_key != model_key:
                raise RuntimeError("CosyVoice runtime profile change requires a process restart")
            return
        with CosyVoiceTtsAdapter._load_lock:
            if CosyVoiceTtsAdapter._model is not None:
                if CosyVoiceTtsAdapter._model_key != model_key:
                    raise RuntimeError("CosyVoice runtime profile change requires a process restart")
                return
            if not self._model_dir.is_dir():
                raise FileNotFoundError(f"CosyVoice model directory is missing: {self._model_dir}")
            if not (self._model_dir / "cosyvoice2.yaml").is_file():
                raise ValueError("model_dir is not a CosyVoice2 checkpoint")
            if not (self._source_dir / "cosyvoice").is_dir():
                raise FileNotFoundError(f"CosyVoice source directory is missing: {self._source_dir}")

            matcha_dir = self._source_dir / "third_party" / "Matcha-TTS"
            for entry in (str(matcha_dir), str(self._source_dir)):
                if entry not in sys.path:
                    sys.path.insert(0, entry)

            # V1 is offline-only.  CosyVoice's optional WeText initializer may
            # otherwise try ModelScope when its FST cache is incomplete.
            os.environ.setdefault("MODELSCOPE_OFFLINE", "1")
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

            from cosyvoice.cli.cosyvoice import CosyVoice2  # type: ignore
            import cosyvoice.cli.frontend as cosy_frontend  # type: ignore
            import cosyvoice.utils.file_utils as cosy_file_utils  # type: ignore

            # torchaudio 2.9 delegates decoding to optional torchcodec.  Keep
            # the upstream tensor contract while decoding with soundfile so
            # every frontend consumer (tokenizer, fbank and speaker encoder)
            # receives the same correctly-resampled torch Tensor.
            cosy_frontend.load_wav = _load_wav_tensor
            cosy_file_utils.load_wav = _load_wav_tensor
            cosy_frontend.CosyVoiceFrontEnd._extract_speech_feat = _extract_speech_feat_tensor
            cosy_frontend.CosyVoiceFrontEnd._extract_spk_embedding = _extract_spk_embedding_tensor

            started = time.perf_counter()
            jit_artifact = self._model_dir / (
                "flow.encoder.fp16.zip" if self._fp16 else "flow.encoder.fp32.zip"
            )
            use_jit = self._load_jit and jit_artifact.is_file()
            trt_status = self._trt_profile.validate() if self._load_trt else {"status": "not_requested"}
            building_trt = self._load_trt and trt_status["status"] == "missing" and self._allow_trt_build
            if self._load_trt and trt_status["status"] != "ready" and not building_trt:
                raise RuntimeError(f"CosyVoice TensorRT engine is not usable: {trt_status['reason']}")
            CosyVoiceTtsAdapter._model = CosyVoice2(
                str(self._model_dir),
                load_jit=use_jit,
                load_trt=self._load_trt,
                load_vllm=False,
                fp16=self._fp16,
            )
            _install_cancellable_llm_inference(
                CosyVoiceTtsAdapter._model,
                self._cancel_event,
            )
            if building_trt:
                self._trt_profile.record_built_engine()
            CosyVoiceTtsAdapter._model_key = model_key
            self.last_metrics["load_ms"] = round((time.perf_counter() - started) * 1000, 1)

    def health(self) -> dict:
        required = ("cosyvoice2.yaml", "llm.pt", "flow.pt", "hift.pt")
        files_ready = self._model_dir.is_dir() and all(
            (self._model_dir / name).is_file() for name in required
        )
        if CosyVoiceTtsAdapter._model is not None:
            status = "ready"
        elif files_ready:
            status = "loading"
        else:
            status = "error"
        return {
            "status": status,
            "logical_id": "cosyvoice2-0.5b",
            "device": "cuda" if self._fp16 else "auto",
            "streaming": self._stream,
            "jit_requested": self._load_jit,
            "trt_requested": self._load_trt,
            "trt_engine_status": self._trt_profile.validate()["status"] if self._load_trt else "not_requested",
        }

    def synthesize_stream(
        self,
        text: str,
        reference_audio_path: str,
        reference_transcript: str,
        max_duration_s: float = 60.0,
    ) -> Iterator[bytes]:
        if not text.strip():
            raise ValueError("text must not be empty")
        if not reference_transcript.strip():
            raise ValueError("reference_transcript is required for zero-shot cloning")
        reference = Path(reference_audio_path).expanduser().resolve()
        if not reference.is_file():
            raise FileNotFoundError(f"reference audio is missing: {reference}")

        self._ensure_loaded()
        model = CosyVoiceTtsAdapter._model
        if model is None:  # defensive guard for type checkers and failed initialization
            raise RuntimeError("CosyVoice2 model did not load")

        # Keeping text_frontend disabled guarantees that inference never tries
        # to download WeText resources at runtime; upstream explicitly
        # supports this mode for benchmark reproduction.
        prompt_wav = str(reference)
        speaker_key = "cw_" + hashlib.sha256(
            reference.read_bytes() + b"\0" + reference_transcript.encode("utf-8")
        ).hexdigest()[:24]
        with CosyVoiceTtsAdapter._speaker_cache_lock:
            if speaker_key not in model.list_available_spks():
                normalized_prompt = model.frontend.text_normalize(
                    reference_transcript,
                    split=False,
                    text_frontend=True,
                )
                model.add_zero_shot_spk(normalized_prompt, prompt_wav, speaker_key)
        self._cancel_event.clear()
        started = time.perf_counter()
        first_packet_ms: float | None = None
        pcm_buffer = bytearray()
        output_bytes = 0

        try:
            outputs = model.inference_zero_shot(
                text,
                reference_transcript,
                prompt_wav,
                zero_shot_spk_id=speaker_key,
                stream=self._stream,
                text_frontend=True,
            )
            for output in outputs:
                if self._cancel_event.is_set():
                    # Keep advancing the upstream generator without emitting
                    # audio.  Its tail joins the internal LLM thread and
                    # removes UUID-scoped caches; abandoning it at the first
                    # cancelled packet leaks native tasks across barge-ins.
                    continue
                speech = output["tts_speech"].detach().float().cpu().numpy()
                pcm = _resample_to_16k_mono_int16(speech, int(model.sample_rate))
                pcm_buffer.extend(pcm.tobytes())
                while len(pcm_buffer) >= FRAME_BYTES:
                    if first_packet_ms is None:
                        first_packet_ms = (time.perf_counter() - started) * 1000
                    frame = bytes(pcm_buffer[:FRAME_BYTES])
                    del pcm_buffer[:FRAME_BYTES]
                    output_bytes += len(frame)
                    yield frame
            if pcm_buffer and not self._cancel_event.is_set():
                pcm_buffer.extend(b"\x00" * (FRAME_BYTES - len(pcm_buffer)))
                if first_packet_ms is None:
                    first_packet_ms = (time.perf_counter() - started) * 1000
                output_bytes += len(pcm_buffer)
                yield bytes(pcm_buffer)
        finally:
            wall_s = time.perf_counter() - started
            audio_s = output_bytes / (16000 * 2)
            self.last_metrics.update(
                {
                    "first_packet_ms": round(first_packet_ms or wall_s * 1000, 1),
                    "wall_ms": round(wall_s * 1000, 1),
                    "audio_s": round(audio_s, 3),
                    "rtf": round(wall_s / audio_s, 4) if audio_s else 0.0,
                    "cancelled": int(self._cancel_event.is_set()),
                    "mode": "streaming" if self._stream else "non_streaming",
                }
            )
            self._logger.emit(
                "tts.synthesize",
                "tts",
                duration_ms=int(wall_s * 1000),
                text_length=len(text),
            )
    def cancel(self, request_id: str) -> bool:
        """Cancel the single in-flight synthesis owned by the speech worker."""
        del request_id  # TtsPort does not yet pass a request id into synthesize_stream.
        self._cancel_event.set()
        return True

    def clear_private_cache(self) -> None:
        """Erase cached user voice features immediately after consent revocation."""
        model = CosyVoiceTtsAdapter._model
        if model is None:
            return
        with CosyVoiceTtsAdapter._speaker_cache_lock:
            for key in list(model.frontend.spk2info):
                if str(key).startswith("cw_"):
                    model.frontend.spk2info.pop(key, None)

    def release_transient_memory(self) -> None:
        """Return completed-turn CPU temporaries without unloading the model.

        CosyVoice creates sizeable NumPy/Torch host buffers while streaming.
        CPython releases the objects after a turn, but glibc may retain their
        arenas indefinitely.  Collection plus ``malloc_trim`` is a Linux-only,
        fail-safe cleanup performed after playback has completed; it never
        changes model residency, precision, or generated audio.
        """
        gc.collect()
        if sys.platform.startswith("linux"):
            try:
                import ctypes

                libc = ctypes.CDLL(None)
                malloc_trim = getattr(libc, "malloc_trim", None)
                if malloc_trim is not None:
                    malloc_trim(0)
            except (AttributeError, OSError):
                pass


def _install_cancellable_llm_inference(model, cancel_event: threading.Event) -> None:
    """Add cooperative cancellation without modifying the pinned dependency."""
    llm = model.model.llm
    if getattr(llm, "_cyberwife_cancel_wrapper", False):
        llm._cyberwife_cancel_event = cancel_event
        return
    original = llm.inference
    llm._cyberwife_cancel_event = cancel_event

    def cancellable_inference(*args, **kwargs):
        for token in original(*args, **kwargs):
            if llm._cyberwife_cancel_event.is_set():
                return
            yield token

    llm.inference = cancellable_inference
    llm._cyberwife_cancel_wrapper = True


def _resample_to_16k_mono_int16(wav: np.ndarray, src_sr: int) -> np.ndarray:
    """Convert ``[channel, sample]``/``[sample]`` float audio to 16 kHz PCM."""
    wav = np.asarray(wav)
    if wav.ndim > 1:
        wav = wav.mean(axis=0 if wav.shape[0] <= wav.shape[-1] else -1)
    wav = wav.astype(np.float32, copy=False).reshape(-1)
    if src_sr != 16000 and wav.size:
        output_size = max(1, round(wav.size * 16000 / src_sr))
        wav = np.interp(
            np.linspace(0, wav.size - 1, output_size),
            np.arange(wav.size),
            wav,
        ).astype(np.float32)
    peak = float(np.max(np.abs(wav))) if wav.size else 0.0
    if peak > 1.0:
        wav = wav / peak
    return np.clip(wav, -1.0, 1.0).__mul__(32767.0).astype(np.int16)


def _load_wav_tensor(wav, target_sr: int, min_sr: int = 16000):
    """SoundFile decoder that preserves CosyVoice's ``[1, samples]`` tensor API."""
    import soundfile as sf
    import torch
    from scipy.signal import resample_poly
    from math import gcd

    samples, sample_rate = sf.read(str(wav), dtype="float32", always_2d=True)
    if sample_rate < min_sr:
        raise ValueError(f"wav sample rate {sample_rate} must be at least {min_sr}")
    samples = samples.mean(axis=1)
    if sample_rate != target_sr:
        divisor = gcd(sample_rate, target_sr)
        samples = resample_poly(
            samples,
            target_sr // divisor,
            sample_rate // divisor,
        ).astype(np.float32)
    return torch.from_numpy(samples).unsqueeze(0)


def _extract_speech_feat_tensor(frontend, prompt_wav):
    """Compatibility replacement for a stale local NumPy/Tensor shim."""
    import torch

    speech = _load_wav_tensor(prompt_wav, 24000)
    speech_feat = frontend.feat_extractor(speech).squeeze(dim=0).transpose(0, 1).to(frontend.device)
    speech_feat = speech_feat.unsqueeze(dim=0)
    speech_feat_len = torch.tensor([speech_feat.shape[1]], dtype=torch.int32).to(frontend.device)
    return speech_feat, speech_feat_len


def _extract_spk_embedding_tensor(frontend, prompt_wav):
    """Compatibility replacement matching the upstream tensor contract."""
    import torch
    import torchaudio.compliance.kaldi as kaldi

    speech = _load_wav_tensor(prompt_wav, 16000)
    feat = kaldi.fbank(speech, num_mel_bins=80, dither=0, sample_frequency=16000)
    feat = feat - feat.mean(dim=0, keepdim=True)
    embedding = frontend.campplus_session.run(
        None,
        {frontend.campplus_session.get_inputs()[0].name: feat.unsqueeze(dim=0).cpu().numpy()},
    )[0].flatten().tolist()
    return torch.tensor([embedding]).to(frontend.device)
