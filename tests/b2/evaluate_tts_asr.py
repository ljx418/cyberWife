"""Evaluate paired generated WAVs with the same real Faster-Whisper model."""
from __future__ import annotations

import csv
import json
import re
import wave
from pathlib import Path
import argparse

from cyberwife.adapters.faster_whisper_adapter import FasterWhisperAdapter


def normalize(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text).lower()


def distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as stream:
        if (stream.getframerate(), stream.getnchannels(), stream.getsampwidth()) != (16000, 1, 2):
            raise RuntimeError(f"unexpected WAV contract: {path}")
        return stream.readframes(stream.getnframes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="audit/v1/B2/tts")
    parser.add_argument("--engines", nargs="+", default=["qwen", "cosyvoice"])
    args = parser.parse_args()
    root = Path(args.root)
    corpus = json.loads(Path("tests/b2/tts_corpus.json").read_text(encoding="utf-8"))
    asr = FasterWhisperAdapter(
        "/mnt/c/ComfyUI-aki-v2/ComfyUI/models/ASR/faster-whisper-large-v3-turbo",
        device="cuda",
        compute_type="float16",
    )
    for engine in args.engines:
        rows = []
        total_errors = total_chars = 0
        for index, target in enumerate(corpus, 1):
            transcript = asr.transcribe(pcm(root / engine / f"{index:02d}.wav")).text
            expected, actual = normalize(target), normalize(transcript)
            errors = distance(expected, actual)
            total_errors += errors
            total_chars += len(expected)
            rows.append({
                "index": index,
                "target": target,
                "transcript": transcript,
                "errors": errors,
                "characters": len(expected),
                "cer": round(errors / max(len(expected), 1), 4),
            })
            print(json.dumps({"engine": engine, **rows[-1]}, ensure_ascii=False), flush=True)
        with (root / engine / "asr.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        (root / engine / "quality.json").write_text(json.dumps({
            "engine": engine,
            "utterances": len(rows),
            "total_errors": total_errors,
            "total_characters": total_chars,
            "cer": round(total_errors / max(total_chars, 1), 4),
            "asr": "faster-whisper-large-v3-turbo/cuda-fp16",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
