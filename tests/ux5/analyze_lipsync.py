"""Relative A/V response analysis for a real UX5 capture.

This deliberately avoids claiming equivalence with the unpublished Wav2Lip
evaluation SyncNet.  It compares the generated lower-face delta against audio
energy and verifies that controlled time shifts score worse than alignment.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import wave
from pathlib import Path

import cv2
import numpy as np


def mirror_index(size: int, index: int) -> int:
    turn, offset = divmod(index, size)
    return offset if turn % 2 == 0 else size - offset - 1


def audio_energy(path: Path, count: int, fps: int = 25) -> np.ndarray:
    with wave.open(str(path), "rb") as stream:
        raw = stream.readframes(stream.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    width = 16000 // fps
    values = []
    for index in range(count):
        chunk = samples[index * width : (index + 1) * width]
        values.append(float(np.sqrt(np.mean(chunk * chunk))) if len(chunk) else 0.0)
    return np.asarray(values, dtype=np.float64)


def generated_delta(video: Path, dataset: Path, sequences: list[int]) -> tuple[np.ndarray, dict]:
    coords = pickle.loads((dataset / "coords.pkl").read_bytes())
    source_files = sorted(
        (dataset / "full_imgs").glob("*.png"), key=lambda path: int(path.stem)
    )
    capture = cv2.VideoCapture(str(video))
    values: list[float] = []
    black = 0
    frozen = 0
    previous_roi = None
    for frame_index, sequence in enumerate(sequences):
        ok, frame = capture.read()
        if not ok:
            break
        if float(frame.mean()) < 2.0:
            black += 1
        source_index = mirror_index(len(source_files), sequence)
        source = cv2.imread(str(source_files[source_index]))
        y1, y2, x1, x2 = coords[source_index]
        mouth_top = y1 + (y2 - y1) // 2
        actual_roi = frame[mouth_top:y2, x1:x2]
        source_roi = source[mouth_top:y2, x1:x2]
        if actual_roi.shape != source_roi.shape or actual_roi.size == 0:
            values.append(0.0)
            continue
        values.append(float(np.mean(cv2.absdiff(actual_roi, source_roi))))
        gray = cv2.cvtColor(actual_roi, cv2.COLOR_BGR2GRAY)
        if previous_roi is not None:
            comparison = cv2.resize(previous_roi, (gray.shape[1], gray.shape[0]))
            if float(np.mean(cv2.absdiff(gray, comparison))) < 0.05:
                frozen += 1
        previous_roi = gray
    capture.release()
    return np.asarray(values), {"decoded_frames": len(values), "black_frames": black, "frozen_pairs": frozen}


def standardize(values: np.ndarray) -> np.ndarray:
    if len(values) == 0 or float(values.std()) < 1e-9:
        return np.zeros_like(values)
    return (values - values.mean()) / values.std()


def correlation_at_shift(audio: np.ndarray, motion: np.ndarray, shift_frames: int) -> float:
    if shift_frames > 0:
        a, m = audio[:-shift_frames], motion[shift_frames:]
    elif shift_frames < 0:
        a, m = audio[-shift_frames:], motion[:shift_frames]
    else:
        a, m = audio, motion
    if len(a) < 8 or float(a.std()) < 1e-9 or float(m.std()) < 1e-9:
        return 0.0
    return float(np.corrcoef(standardize(a), standardize(m))[0, 1])


def analyze(args: argparse.Namespace) -> dict:
    rows = list(csv.DictReader((args.capture / "video-timeline.csv").open(encoding="utf-8")))
    sequences = [int(row["sequence"]) for row in rows]
    motion, visual = generated_delta(args.capture / "lipsync-review.mp4", args.dataset, sequences)
    energy = audio_energy(args.wav, len(motion))
    usable = min(len(motion), len(energy))
    motion, energy = motion[:usable], energy[:usable]
    search = {offset: correlation_at_shift(energy, motion, round(offset / 40)) for offset in range(-400, 401, 40)}
    best_offset = max(search, key=search.get)
    controls = {offset: correlation_at_shift(energy, motion, round(offset / 40)) for offset in (-400, -200, 0, 200, 400)}
    voiced = energy > max(0.002, float(np.percentile(energy, 35)))
    voiced_motion = float(motion[voiced].mean()) if np.any(voiced) else 0.0
    silent_motion = float(motion[~voiced].mean()) if np.any(~voiced) else 0.0
    report = {
        "schema_version": 1,
        "method": "lower-face generated-delta versus 40ms RMS; relative diagnostic only",
        "frames_analyzed": usable,
        "best_offset_ms": best_offset,
        "best_correlation": round(search[best_offset], 6),
        "controlled_shift_correlations": {key: round(value, 6) for key, value in controls.items()},
        "voiced_motion_mean": round(voiced_motion, 6),
        "silent_motion_mean": round(silent_motion, 6),
        "voiced_to_silent_ratio": round(voiced_motion / silent_motion, 6) if silent_motion > 0 else math.inf,
        "visual": visual,
        "gates": {
            "best_offset_within_80ms": abs(best_offset) <= 80,
            "zero_beats_200ms_controls": controls[0] >= max(controls[-200], controls[200]),
            "zero_beats_400ms_controls": controls[0] >= max(controls[-400], controls[400]),
            "mouth_responds_during_voice": voiced_motion > silent_motion * 1.10,
            "no_black_frames": visual["black_frames"] == 0,
        },
        "limitations": [
            "This is not the unpublished Wav2Lip evaluation SyncNet.",
            "Automated motion correlation cannot replace human phoneme/naturalness review.",
        ],
    }
    report["automated_pass"] = all(report["gates"].values())
    (args.capture / "analysis-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(analyze(parse_args()), ensure_ascii=False, indent=2))
