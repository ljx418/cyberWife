"""Real Qwen3-TTS voice-clone probe; no mock may promote TTS to ready."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

from cyberwife.adapters.qwen_tts_adapter import QwenTtsAdapter
from tests.m0 import load_registry


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    entry = load_registry().get("qwen3-tts-12hz-1.7b-base", {})
    model_dir = str(entry.get("absolute_path", ""))
    reference = Path(os.environ.get("CW_TTS_REFERENCE_AUDIO", repo_root / "assets" / "voice" / "user_clip_v2.wav"))
    reference_text = os.environ.get(
        "CW_TTS_REFERENCE_TEXT",
        "早上好，宝贝，快起床了，起来陪我玩",
    )
    if not reference.is_file():
        print(json.dumps({"logical_id": "qwen3-tts-12hz-1.7b-base", "status": "blocked", "reason": "reference_audio_missing"}, ensure_ascii=False))
        return 1
    started = time.perf_counter()
    try:
        adapter = QwenTtsAdapter(model_dir=model_dir, device="cuda", dtype="bf16")
        frames = list(adapter.synthesize_stream(
            "你好。",
            str(reference),
            reference_text,
            max_duration_s=5.0,
        ))
        if not frames or any(len(frame) != 640 for frame in frames):
            raise RuntimeError("TTS did not emit 20ms/640-byte PCM frames")
        pcm = np.frombuffer(b"".join(frames), dtype=np.int16)
        if not pcm.size or int(np.max(np.abs(pcm.astype(np.int32)))) < 128:
            raise RuntimeError("TTS output is empty or effectively silent")
        result = {
            "logical_id": "qwen3-tts-12hz-1.7b-base",
            "status": "verified",
            "device": "cuda",
            "dtype": "bf16",
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "frames": len(frames),
            "frame_bytes": 640,
            "peak_abs": int(np.max(np.abs(pcm.astype(np.int32)))),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({
            "logical_id": "qwen3-tts-12hz-1.7b-base",
            "status": "blocked",
            "reason": f"{type(exc).__name__}: {str(exc)[:300]}",
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
