"""Run a reproducible CosyVoice2 vs existing-Qwen audio benchmark.

This script deliberately writes only derived audio and aggregate measurements;
it never copies the reference recording into the audit directory.
"""
from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np


def audio_metrics(path: Path) -> dict[str, float | int | str]:
    import soundfile as sf

    samples, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    channels = samples.shape[1]
    normalized = samples.reshape(-1)
    pcm = np.clip(normalized, -1.0, 1.0).__mul__(32767.0).astype(np.int16)
    rms = float(np.sqrt(np.mean(normalized**2))) if normalized.size else 0.0
    active_ratio = float(np.mean(np.abs(normalized) >= 10 ** (-40 / 20))) if normalized.size else 0.0
    clipping_ratio = float(np.mean(np.abs(pcm.astype(np.int32)) >= 32760)) if pcm.size else 0.0
    return {
        "file": str(path),
        "sample_rate": sample_rate,
        "channels": channels,
        "duration_s": round(samples.shape[0] / max(sample_rate, 1), 3),
        "rms_dbfs": round(20 * np.log10(max(rms, 1e-12)), 2),
        "active_ratio": round(active_ratio, 4),
        "clipping_ratio": round(clipping_ratio, 6),
        "peak": int(np.max(np.abs(pcm.astype(np.int32)))) if pcm.size else 0,
    }


def write_pcm_wav(path: Path, frames: list[bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"".join(frames))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-text", required=True)
    parser.add_argument("--text", default="今天天气不错，我想和你聊聊天")
    parser.add_argument("--output", default="audit/cosyvoice2_t1.wav")
    parser.add_argument("--report", default="audit/cosyvoice-comparison.json")
    parser.add_argument("--qwen-baseline", default="audit/tts_ns_ns_t1.wav")
    parser.add_argument("--no-fp16", action="store_true")
    parser.add_argument("--jit", action="store_true")
    parser.add_argument("--non-streaming", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    from cyberwife.adapters.cosyvoice_tts_adapter import CosyVoiceTtsAdapter

    import random
    import torch

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    adapter = CosyVoiceTtsAdapter(
        args.model_dir,
        source_dir=args.source_dir,
        fp16=not args.no_fp16,
        stream=not args.non_streaming,
        load_jit=args.jit,
    )

    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        torch = None  # type: ignore

    started = time.perf_counter()
    frames = list(
        adapter.synthesize_stream(
            args.text,
            args.reference,
            args.reference_text,
        )
    )
    elapsed_s = time.perf_counter() - started
    output = Path(args.output)
    write_pcm_wav(output, frames)

    cosy = audio_metrics(output)
    cosy.update(adapter.last_metrics)
    cosy["mode"] = "non_streaming" if args.non_streaming else "streaming"
    cosy["end_to_end_wall_s"] = round(elapsed_s, 3)
    if torch is not None and torch.cuda.is_available():
        cosy["gpu_peak_allocated_gib"] = round(torch.cuda.max_memory_allocated() / 1024**3, 3)
        cosy["gpu_peak_reserved_gib"] = round(torch.cuda.max_memory_reserved() / 1024**3, 3)

    baseline = Path(args.qwen_baseline)
    report = {
        "schema_version": 1,
        "input": {
            "text": args.text,
            "reference_duration_s": audio_metrics(Path(args.reference))["duration_s"],
        },
        "cosyvoice2": cosy,
        "qwen3_tts_existing": audio_metrics(baseline) if baseline.is_file() else None,
        "comparison_note": "Objective waveform/timing metrics are not a MOS score; use the paired WAV files for blind listening.",
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
