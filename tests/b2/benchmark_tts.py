"""Generate the paired 30-utterance Qwen/CosyVoice B2 corpus."""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
import wave
from pathlib import Path


def write_wav(path: Path, frames) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        for frame in frames:
            if len(frame) != 640:
                raise RuntimeError(f"invalid PCM frame size: {len(frame)}")
            stream.writeframes(frame)
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=("qwen", "cosyvoice", "cosyvoice-trt"), required=True)
    parser.add_argument("--reference", default="assets/voice/user_clip_v2.wav")
    parser.add_argument("--reference-text", default="早上好，宝贝，快起床了，起来陪我玩")
    parser.add_argument("--corpus", default="tests/b2/tts_corpus.json")
    parser.add_argument("--output-root", default="audit/v1/B2/tts")
    args = parser.parse_args()

    if args.engine == "qwen":
        from cyberwife.adapters.qwen_tts_adapter import QwenTtsAdapter
        adapter = QwenTtsAdapter(
            "/mnt/c/ComfyUI-aki-v2/ComfyUI/models/TTS/Qwen3-TTS-12Hz-1.7B-Base",
            device="cuda",
            dtype="bf16",
        )
    else:
        from cyberwife.adapters.cosyvoice_tts_adapter import CosyVoiceTtsAdapter
        adapter = CosyVoiceTtsAdapter(
            "/home/administrator/.cyberWife/models/tts/CosyVoice2-0.5B",
            source_dir="/home/administrator/.cyberWife/src/CosyVoice",
            fp16=True,
            stream=True,
            load_trt=args.engine == "cosyvoice-trt",
        )

    texts = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    root = Path(args.output_root) / args.engine
    rows = []
    for index, target in enumerate(texts, 1):
        started = time.perf_counter()
        frames = write_wav(
            root / f"{index:02d}.wav",
            adapter.synthesize_stream(target, args.reference, args.reference_text),
        )
        wall_ms = round((time.perf_counter() - started) * 1000, 1)
        metrics = dict(getattr(adapter, "last_metrics", {}))
        rows.append({
            "index": index,
            "target": target,
            "frames": frames,
            "audio_ms": frames * 20,
            "wall_ms": wall_ms,
            "first_packet_ms": metrics.get("first_packet_ms", wall_ms),
            "rtf": metrics.get("rtf", round(wall_ms / max(frames * 20, 1), 4)),
        })
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    report = root / "latency.csv"
    with report.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
