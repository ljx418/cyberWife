"""Build and verify the removable CosyVoice2 FP16 TensorRT flow engine."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from cyberwife.adapters.cosyvoice_tts_adapter import CosyVoiceTtsAdapter  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--reference-audio", required=True)
    parser.add_argument("--reference-text", required=True)
    args = parser.parse_args()

    adapter = CosyVoiceTtsAdapter(
        args.model_dir,
        source_dir=args.source_dir,
        fp16=True,
        stream=True,
        load_trt=True,
        allow_trt_build=True,
    )
    started = time.perf_counter()
    frames = list(
        adapter.synthesize_stream(
            "你好。", args.reference_audio, args.reference_text, max_duration_s=30.0,
        )
    )
    if not frames or not any(any(frame) for frame in frames):
        raise SystemExit("TensorRT smoke produced no non-silent PCM")
    print(json.dumps({
        "status": "ready",
        "frame_count": len(frames),
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        "adapter_metrics": adapter.last_metrics,
        "health": adapter.health(),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
