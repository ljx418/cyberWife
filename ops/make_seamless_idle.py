#!/usr/bin/env python3
"""Convert an approved idle clip into an exact 10-second palindrome loop."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np


def read_frames(path: Path) -> tuple[list[np.ndarray], float]:
    capture = cv2.VideoCapture(str(path))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frames: list[np.ndarray] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    if not frames or fps <= 0:
        raise RuntimeError(f"cannot decode source video: {path}")
    return frames, fps


def palindrome_frames(frames: list[np.ndarray], half_frames: int = 80) -> list[np.ndarray]:
    if len(frames) < half_frames:
        raise ValueError(f"source requires at least {half_frames} frames")
    forward = frames[:half_frames]
    return forward + list(reversed(forward))


def mean_absolute_error(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(np.abs(left.astype(np.float32) - right.astype(np.float32))))


def encode(frames: list[np.ndarray], output: Path, fps: int = 16) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix="cw-idle-loop-"))
    try:
        for index, frame in enumerate(frames):
            if not cv2.imwrite(str(temporary / f"{index:06d}.png"), frame):
                raise RuntimeError(f"failed to write temporary frame {index}")
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-framerate", str(fps), "-i", str(temporary / "%06d.png"),
            "-c:v", "libx264", "-preset", "medium", "-crf", "16",
            "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart",
            str(output),
        ]
        subprocess.run(command, check=True)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metrics", type=Path)
    args = parser.parse_args()

    source, source_fps = read_frames(args.input)
    loop = palindrome_frames(source)
    if not np.array_equal(loop[0], loop[-1]):
        raise RuntimeError("pre-encode loop endpoints are not identical")
    if not np.array_equal(loop[79], loop[80]):
        raise RuntimeError("pre-encode turnaround frames are not identical")
    encode(loop, args.output)
    decoded, output_fps = read_frames(args.output)
    if len(decoded) != 160 or abs(output_fps - 16.0) > 0.05:
        raise RuntimeError(f"unexpected encoded contract: {len(decoded)} @ {output_fps}")
    metrics = {
        "source": str(args.input),
        "output": str(args.output),
        "source_frames": len(source),
        "source_fps": round(source_fps, 3),
        "output_frames": len(decoded),
        "output_fps": round(output_fps, 3),
        "duration_seconds": round(len(decoded) / output_fps, 3),
        "first_last_mae": round(mean_absolute_error(decoded[0], decoded[-1]), 4),
        "turnaround_mae": round(mean_absolute_error(decoded[79], decoded[80]), 4),
        "construction": "80_forward_plus_80_reverse",
    }
    if metrics["first_last_mae"] > 3.0 or metrics["turnaround_mae"] > 3.0:
        raise RuntimeError(f"encoded loop seam exceeds threshold: {metrics}")
    if args.metrics:
        args.metrics.parent.mkdir(parents=True, exist_ok=True)
        args.metrics.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
