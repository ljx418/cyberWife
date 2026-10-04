"""Loopback-only speech runtime and model functional-probe service.

Raw microphone PCM is accepted only in memory, with a strict duration/format
limit.  No endpoint accepts a filesystem path from a client.
"""
from __future__ import annotations

import argparse
import asyncio
import gc
import sys
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
import uvicorn

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from cyberwife.application.functional_probes import FunctionalProbeRunner  # noqa: E402
from cyberwife.application.model_registry import ModelRegistry  # noqa: E402


PCM_BYTES_PER_SECOND = 16000 * 1 * 2
MAX_UTTERANCE_SECONDS = 30
MAX_UTTERANCE_BYTES = PCM_BYTES_PER_SECOND * MAX_UTTERANCE_SECONDS


class SpeechRuntime:
    """Lazy, single-user VAD/ASR runtime with bounded model residency."""

    def __init__(
        self,
        model_dir: str,
        *,
        asr_device: str = "cpu",
        asr_compute_type: str = "int8",
        vad_factory=None,
        asr_factory=None,
        embedding_factory=None,
    ) -> None:
        self._model_dir = model_dir
        self._asr_device = asr_device
        self._asr_compute_type = asr_compute_type
        self._vad_factory = vad_factory
        self._asr_factory = asr_factory
        self._embedding_factory = embedding_factory
        self._vad = None
        self._asr = None
        self._embedding = None
        self._load_lock = threading.RLock()
        self._infer_lock = threading.Lock()

    def _get_vad(self):
        if self._vad is None:
            with self._load_lock:
                if self._vad is None:
                    if self._vad_factory is not None:
                        self._vad = self._vad_factory()
                    else:
                        from cyberwife.adapters.silero_vad_adapter import SileroVadAdapter

                        self._vad = SileroVadAdapter()
        return self._vad

    def _get_asr(self):
        if self._asr is None:
            with self._load_lock:
                if self._asr is None:
                    if self._asr_factory is not None:
                        self._asr = self._asr_factory()
                    else:
                        from cyberwife.adapters.faster_whisper_adapter import FasterWhisperAdapter

                        self._asr = FasterWhisperAdapter(
                            self._model_dir,
                            device=self._asr_device,
                            compute_type=self._asr_compute_type,
                        )
        return self._asr

    def _get_embedding(self):
        if self._embedding is None:
            with self._load_lock:
                if self._embedding is None:
                    if self._embedding_factory is not None:
                        self._embedding = self._embedding_factory()
                    else:
                        from cyberwife.adapters.bge_embedding_adapter import BgeEmbeddingAdapter

                        entry = ModelRegistry(REPO_ROOT).get("bge-small-zh-v1.5")
                        if entry is None:
                            raise RuntimeError("embedding model is absent from registry")
                        self._embedding = BgeEmbeddingAdapter(entry.absolute_path, device="cpu")
        return self._embedding

    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> dict:
        if sample_rate != 16000:
            raise ValueError("only 16000Hz PCM is accepted")
        if len(pcm) < 640 or len(pcm) % 640:
            raise ValueError("PCM must contain whole 20ms/640-byte frames")
        if len(pcm) > MAX_UTTERANCE_BYTES:
            raise ValueError("utterance exceeds 30 seconds")
        started = time.perf_counter()
        with self._infer_lock:
            vad_events = self._get_vad().speech_timestamps(pcm, sample_rate)
            if not vad_events:
                return {
                    "speech_detected": False,
                    "text": "",
                    "confidence": 0.0,
                    "language": "zh",
                    "segments": [],
                    "vad_segments": [],
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                }
            result = self._get_asr().transcribe(pcm, sample_rate)
        return {
            "speech_detected": True,
            "text": result.text,
            "confidence": result.confidence,
            "language": result.language,
            "segments": [
                {
                    "start_ms": segment.start_ms,
                    "end_ms": segment.end_ms,
                    "text": segment.text,
                    "confidence": segment.confidence,
                }
                for segment in result.segments
            ],
            "vad_segments": [event.to_dict() for event in vad_events],
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        with self._infer_lock:
            return self._get_embedding().embed_batch(texts)

    def warm(self) -> None:
        """Load every V1 speech model before the process becomes reachable."""
        with self._infer_lock:
            silence = b"\0" * PCM_BYTES_PER_SECOND
            self._get_vad().speech_timestamps(silence, 16000)
            # Bypass VAD for this private synthetic warm-up so the ASR engine
            # allocates its real inference workspace without user audio.
            self._get_asr().transcribe(silence, 16000)
            self._get_embedding().embed_batch(["本地预热"])
        self.release_transient_memory()

    def release_transient_memory(self) -> None:
        """Release completed ASR/embedding host temporaries, keep models warm."""
        gc.collect()
        if sys.platform.startswith("linux"):
            try:
                import ctypes

                malloc_trim = getattr(ctypes.CDLL(None), "malloc_trim", None)
                if malloc_trim is not None:
                    malloc_trim(0)
            except (AttributeError, OSError):
                pass


def build_app(timeout_s: float = 120.0, runtime: SpeechRuntime | None = None) -> FastAPI:
    app = FastAPI(title="cyberWife Speech Runtime", version="1.0.0")
    runner = FunctionalProbeRunner(REPO_ROOT, speech_url=None, timeout_s=timeout_s)
    states = {name: {"status": "loading", "last_error": "probe_not_run"} for name in ("vad", "asr", "tts", "embedding")}
    if runtime is None:
        registry = ModelRegistry(REPO_ROOT)
        asr_entry = registry.get("faster-whisper-large-v3-turbo")
        if asr_entry is None:
            raise RuntimeError("ASR model is absent from registry")
        runtime = SpeechRuntime(asr_entry.absolute_path)

    @app.get("/health")
    async def health() -> dict:
        statuses = [value["status"] for value in states.values()]
        overall = "ready" if statuses and all(value == "ready" for value in statuses) else "error" if any(value == "error" for value in statuses) else "loading"
        return {"status": overall, "components": states}

    @app.post("/api/v1/probe/{component}")
    async def probe(component: str) -> dict:
        if component not in states:
            raise HTTPException(status_code=404, detail="unknown_component")
        import asyncio
        result = await asyncio.to_thread(runner.run, component)
        payload = {
            "status": result.status,
            "logical_id": result.logical_id or component,
            "latency_ms": result.latency_ms,
            "checked_at": result.checked_at.isoformat(),
            "device": result.device,
            "dtype": result.dtype,
            "error": result.error,
        }
        states[component] = payload
        return payload

    @app.post("/api/v1/utterances/transcribe")
    async def transcribe_utterance(request: Request) -> dict:
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        if content_type != "application/octet-stream":
            raise HTTPException(status_code=415, detail="pcm_content_type_required")
        if request.headers.get("x-audio-channels", "1") != "1":
            raise HTTPException(status_code=422, detail="mono_audio_required")
        try:
            sample_rate = int(request.headers.get("x-sample-rate", "16000"))
        except ValueError:
            raise HTTPException(status_code=422, detail="invalid_sample_rate")
        pcm = await request.body()
        if len(pcm) > MAX_UTTERANCE_BYTES:
            raise HTTPException(status_code=413, detail="utterance_too_large")
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(runtime.transcribe, pcm, sample_rate),
                timeout=timeout_s,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except TimeoutError:
            raise HTTPException(status_code=504, detail="asr_timeout")
        await asyncio.to_thread(runtime.release_transient_memory)
        for component in ("vad", "asr"):
            states[component] = {
                "status": "ready",
                "last_error": None,
                "latency_ms": result["latency_ms"],
            }
        return result

    @app.post("/api/v1/embeddings")
    async def embeddings(payload: dict) -> dict:
        texts = payload.get("texts")
        if not isinstance(texts, list) or not texts or len(texts) > 32:
            raise HTTPException(status_code=422, detail="texts_must_contain_1_to_32_items")
        if any(not isinstance(text, str) or not text.strip() or len(text) > 2000 for text in texts):
            raise HTTPException(status_code=422, detail="embedding_text_invalid")
        started = time.perf_counter()
        vectors = await asyncio.wait_for(
            asyncio.to_thread(runtime.embed_batch, texts), timeout=timeout_s
        )
        await asyncio.to_thread(runtime.release_transient_memory)
        states["embedding"] = {
            "status": "ready",
            "last_error": None,
            "latency_ms": round((time.perf_counter() - started) * 1000),
        }
        return {
            "logical_id": "bge-small-zh-v1.5",
            "embedding_dim": 512,
            "vectors": vectors,
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="cyberWife speech runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--probe-timeout", type=float, default=120.0)
    parser.add_argument("--asr-device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--asr-compute-type", default="int8")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("speech runtime must bind loopback")
    registry = ModelRegistry(REPO_ROOT)
    asr_entry = registry.get("faster-whisper-large-v3-turbo")
    if asr_entry is None:
        raise SystemExit("ASR model is absent from registry")
    runtime = SpeechRuntime(
        asr_entry.absolute_path,
        asr_device=args.asr_device,
        asr_compute_type=args.asr_compute_type,
    )
    runtime.warm()
    uvicorn.run(build_app(args.probe_timeout, runtime), host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
