"""Run the public Oxford SyncNet as a calibrated, non-release diagnostic."""

from __future__ import annotations

import argparse
import csv
import json
import pickle
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from tests.ux5.analyze_lipsync import mirror_index


def crop_face_video(capture: Path, dataset: Path, output: Path) -> int:
    rows = list(csv.DictReader((capture / "video-timeline.csv").open(encoding="utf-8")))
    sequences = [int(row["sequence"]) for row in rows]
    coords = pickle.loads((dataset / "coords.pkl").read_bytes())
    source_count = len(list((dataset / "full_imgs").glob("*.png")))
    reader = cv2.VideoCapture(str(capture / "lipsync-review.mp4"))
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"MJPG"), 25, (224, 224))
    written = 0
    for sequence in sequences:
        ok, frame = reader.read()
        if not ok:
            break
        index = mirror_index(source_count, sequence)
        y1, y2, x1, x2 = coords[index]
        size = max(y2 - y1, x2 - x1) / 2.0
        center_y, center_x = (y1 + y2) / 2.0, (x1 + x2) / 2.0
        radius = int(size * 1.4)
        padded = cv2.copyMakeBorder(frame, radius, radius, radius, radius, cv2.BORDER_CONSTANT, value=(110, 110, 110))
        cy, cx = int(center_y + radius), int(center_x + radius)
        face = padded[cy - radius : cy + radius, cx - radius : cx + radius]
        writer.write(cv2.resize(face, (224, 224)))
        written += 1
    reader.release()
    writer.release()
    return written


def shifted_wav(source: Path, output: Path, shift_ms: int, duration_frames: int) -> None:
    with wave.open(str(source), "rb") as stream:
        audio = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2")
    total = duration_frames * 640
    base = np.zeros(total, dtype=np.int16)
    base[: min(total, len(audio))] = audio[:total]
    shifted = np.zeros_like(base)
    samples = round(shift_ms * 16)
    if samples > 0:
        shifted[samples:] = base[:-samples]
    elif samples < 0:
        shifted[:samples] = base[-samples:]
    else:
        shifted[:] = base
    with wave.open(str(output), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(shifted.tobytes())


def mux(video: Path, audio: Path, output: Path) -> None:
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video), "-i", str(audio),
        "-c:v", "copy", "-c:a", "pcm_s16le", "-shortest", str(output),
    ], check=True)


def main(args: argparse.Namespace) -> dict:
    args.output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(args.dependency_root))
    sys.path.insert(0, str(args.syncnet_root))
    from SyncNetInstance import SyncNetInstance  # type: ignore

    silent_video = args.output / "face-only.avi"
    frame_count = crop_face_video(args.capture, args.dataset, silent_video)
    evaluator = SyncNetInstance()
    evaluator.loadParameters(str(args.model))
    results: dict[str, dict] = {}
    for shift_ms in (-400, -200, 0, 200, 400):
        wav = args.output / f"audio-{shift_ms:+d}.wav"
        video = args.output / f"syncnet-{shift_ms:+d}.avi"
        shifted_wav(args.wav, wav, shift_ms, frame_count)
        mux(silent_video, wav, video)
        options = SimpleNamespace(
            tmp_dir=str(args.output / "tmp"), reference=f"shift-{shift_ms:+d}", batch_size=20, vshift=15
        )
        offset, confidence, _ = evaluator.evaluate(options, str(video))
        results[str(shift_ms)] = {
            "detected_offset_frames": int(offset),
            "detected_offset_ms": int(offset) * 40,
            "confidence": round(float(confidence), 6),
        }
    baseline = results["0"]["detected_offset_ms"]
    deltas = {
        key: value["detected_offset_ms"] - baseline for key, value in results.items()
    }
    # Positive audio delay should move the detected offset by the same number
    # of 40ms frames, modulo SyncNet's sign convention determined by controls.
    orientation = 1 if deltas["200"] > deltas["-200"] else -1
    calibration_errors = {
        key: abs(delta - orientation * int(key)) for key, delta in deltas.items() if key != "0"
    }
    report = {
        "schema_version": 1,
        "tool": "public Oxford SyncNet syncnet_v2",
        "scope": "diagnostic; not the unpublished Wav2Lip benchmark evaluator",
        "frames": frame_count,
        "results": results,
        "baseline_offset_ms": baseline,
        "control_orientation": orientation,
        "control_delta_ms": deltas,
        "calibration_error_ms": calibration_errors,
        "gates": {
            "baseline_within_80ms": abs(baseline) <= 80,
            "controls_track_injected_shift": all(error <= 40 for error in calibration_errors.values()),
            "baseline_confidence_positive": results["0"]["confidence"] > 0,
        },
    }
    report["diagnostic_pass"] = all(report["gates"].values())
    (args.output / "syncnet-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--syncnet-root", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(main(parse_args()), ensure_ascii=False, indent=2))
