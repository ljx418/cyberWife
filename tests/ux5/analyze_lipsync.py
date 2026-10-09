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


def generated_delta(video: Path, dataset: Path, sequences: list[int]) -> tuple[np.ndarray, dict, dict]:
    coords = pickle.loads((dataset / "coords.pkl").read_bytes())
    manifest_path = dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    muse_coordinates = str(manifest.get("engine", "")).startswith("musetalk")
    source_files = sorted(
        (dataset / "full_imgs").glob("*.png"), key=lambda path: int(path.stem)
    )
    capture = cv2.VideoCapture(str(video))
    values: list[float] = []
    black = 0
    frozen = 0
    frozen_run = 0
    max_frozen_run = 0
    previous_roi = None
    previous_face = None
    previous_previous_face = None
    boundary_delta: list[float] = []
    boundary_excess: list[float] = []
    upper_face_identity_delta: list[float] = []
    frame_motion: list[float] = []
    second_order_motion: list[float] = []
    sharpness: list[float] = []
    mouth_frame_motion: list[float] = []
    mouth_second_order_motion: list[float] = []
    previous_mouth = None
    previous_previous_mouth = None
    for frame_index, sequence in enumerate(sequences):
        ok, frame = capture.read()
        if not ok:
            break
        if float(frame.mean()) < 2.0:
            black += 1
        source_index = mirror_index(len(source_files), sequence)
        source = cv2.imread(str(source_files[source_index]))
        if muse_coordinates:
            x1, y1, x2, y2 = coords[source_index]
        else:
            y1, y2, x1, x2 = coords[source_index]
        mouth_top = y1 + (y2 - y1) // 2
        actual_roi = frame[mouth_top:y2, x1:x2]
        source_roi = source[mouth_top:y2, x1:x2]
        if actual_roi.shape != source_roi.shape or actual_roi.size == 0:
            values.append(0.0)
            continue
        values.append(float(np.mean(cv2.absdiff(actual_roi, source_roi))))
        actual_face = frame[y1:y2, x1:x2]
        source_face = source[y1:y2, x1:x2]
        if actual_face.size and actual_face.shape == source_face.shape:
            face_height, face_width = actual_face.shape[:2]
            upper_end = max(1, round(face_height * 0.42))
            upper_actual = actual_face[:upper_end]
            upper_source = source_face[:upper_end]
            upper_face_identity_delta.append(
                float(np.mean(cv2.absdiff(upper_actual, upper_source)))
            )
            band = max(2, round(face_width * 0.12))
            top = round(face_height * 0.35)
            sides_actual = np.concatenate(
                (actual_face[top:, :band], actual_face[top:, -band:]), axis=1,
            )
            sides_source = np.concatenate(
                (source_face[top:, :band], source_face[top:, -band:]), axis=1,
            )
            boundary_delta.append(float(np.mean(cv2.absdiff(sides_actual, sides_source))))
            controls_actual = []
            controls_source = []
            if x1 - band >= 0:
                controls_actual.append(frame[y1 + top:y2, x1 - band:x1])
                controls_source.append(source[y1 + top:y2, x1 - band:x1])
            if x2 + band <= frame.shape[1]:
                controls_actual.append(frame[y1 + top:y2, x2:x2 + band])
                controls_source.append(source[y1 + top:y2, x2:x2 + band])
            if controls_actual:
                control_actual = np.concatenate(controls_actual, axis=1)
                control_source = np.concatenate(controls_source, axis=1)
                codec_floor = float(np.mean(cv2.absdiff(control_actual, control_source)))
                boundary_excess.append(max(0.0, boundary_delta[-1] - codec_floor))
            face_gray = cv2.cvtColor(actual_face, cv2.COLOR_BGR2GRAY)
            face_gray = cv2.resize(face_gray, (128, 128), interpolation=cv2.INTER_AREA).astype(np.float32)
            sharpness.append(float(cv2.Laplacian(face_gray, cv2.CV_32F).var()))
            if previous_face is not None:
                frame_motion.append(float(np.mean(np.abs(face_gray - previous_face))))
            if previous_face is not None and previous_previous_face is not None:
                second_order_motion.append(float(np.mean(np.abs(face_gray - 2 * previous_face + previous_previous_face))))
            previous_previous_face = previous_face
            previous_face = face_gray
        gray = cv2.cvtColor(actual_roi, cv2.COLOR_BGR2GRAY)
        mouth = cv2.resize(gray, (128, 64), interpolation=cv2.INTER_AREA).astype(np.float32)
        if previous_mouth is not None:
            mouth_frame_motion.append(float(np.mean(np.abs(mouth - previous_mouth))))
        if previous_mouth is not None and previous_previous_mouth is not None:
            mouth_second_order_motion.append(
                float(np.mean(np.abs(mouth - 2 * previous_mouth + previous_previous_mouth)))
            )
        previous_previous_mouth = previous_mouth
        previous_mouth = mouth
        if previous_roi is not None:
            comparison = cv2.resize(previous_roi, (gray.shape[1], gray.shape[0]))
            if float(np.mean(cv2.absdiff(gray, comparison))) < 0.05:
                frozen += 1
                frozen_run += 1
                max_frozen_run = max(max_frozen_run, frozen_run)
            else:
                frozen_run = 0
        previous_roi = gray
    capture.release()
    def summary(values: list[float]) -> dict[str, float]:
        data = np.asarray(values, dtype=np.float64)
        return {
            "mean": round(float(data.mean()), 6) if len(data) else 0.0,
            "p95": round(float(np.percentile(data, 95)), 6) if len(data) else 0.0,
        }

    return np.asarray(values), {
        "decoded_frames": len(values),
        "black_frames": black,
        "frozen_pairs": frozen,
        "frozen_pair_rate": round(frozen / max(1, len(values) - 1), 6),
        "max_consecutive_frozen_pairs": max_frozen_run,
        "cheek_boundary_delta": summary(boundary_delta),
        "cheek_boundary_excess_over_codec_floor": summary(boundary_excess),
        "upper_face_identity_delta": summary(upper_face_identity_delta),
        "face_frame_motion": summary(frame_motion),
        "face_second_order_motion": summary(second_order_motion),
        "face_sharpness": summary(sharpness),
        "mouth_frame_motion": summary(mouth_frame_motion),
        "mouth_second_order_motion": summary(mouth_second_order_motion),
    }, {
        "mouth_frame_motion": np.asarray(mouth_frame_motion, dtype=np.float64),
        "mouth_second_order_motion": np.asarray(mouth_second_order_motion, dtype=np.float64),
    }


def post_speech_metrics(
    energy: np.ndarray,
    mouth_delta: np.ndarray,
    mouth_second_order: np.ndarray,
    *,
    fps: int = 25,
) -> dict:
    """Measure the local tail after the final audible phoneme."""
    count = min(len(energy), len(mouth_delta))
    energy = energy[:count]
    mouth_delta = mouth_delta[:count]
    voiced = energy >= 0.005
    voiced_indices = np.flatnonzero(voiced)
    if not len(voiced_indices):
        return {"evaluable": False, "reason": "no_voiced_audio"}
    grace_frames = max(1, round(0.16 * fps))
    tail_start = int(voiced_indices[-1]) + 1 + grace_frames
    tail = mouth_delta[tail_start:count]
    if len(tail) < round(0.4 * fps):
        return {
            "evaluable": False,
            "reason": "less_than_400ms_post_speech_silence",
            "last_voiced_ms": int((voiced_indices[-1] + 1) * 1000 / fps),
        }
    voiced_delta = mouth_delta[voiced]
    second_tail = mouth_second_order[max(0, tail_start - 2):max(0, count - 2)]
    voiced_second = mouth_second_order[:max(0, int(voiced_indices[-1]) - 1)]
    delta_mean = float(tail.mean())
    voiced_mean = float(voiced_delta.mean()) if len(voiced_delta) else 0.0
    second_mean = float(second_tail.mean()) if len(second_tail) else 0.0
    voiced_second_mean = float(voiced_second.mean()) if len(voiced_second) else 0.0
    return {
        "evaluable": True,
        "last_voiced_ms": int((voiced_indices[-1] + 1) * 1000 / fps),
        "tail_start_ms": int(tail_start * 1000 / fps),
        "tail_duration_ms": int(len(tail) * 1000 / fps),
        "mouth_delta_mean": round(delta_mean, 6),
        "voiced_mouth_delta_mean": round(voiced_mean, 6),
        "mouth_delta_ratio": round(delta_mean / voiced_mean, 6) if voiced_mean else math.inf,
        "second_order_mean": round(second_mean, 6),
        "voiced_second_order_mean": round(voiced_second_mean, 6),
        "second_order_ratio": (
            round(second_mean / voiced_second_mean, 6) if voiced_second_mean else math.inf
        ),
    }


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


def max_consecutive_voiced_freeze(
    energy: np.ndarray,
    mouth_frame_motion: np.ndarray,
    *,
    threshold: float = 0.05,
) -> int:
    """Count freezes only while either side of a frame pair is voiced."""
    longest = 0
    current = 0
    usable = min(len(mouth_frame_motion), max(0, len(energy) - 1))
    for index in range(usable):
        voiced_pair = energy[index] >= 0.005 or energy[index + 1] >= 0.005
        if voiced_pair and mouth_frame_motion[index] < threshold:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def mouth_motion_pass(report: dict) -> bool:
    """Return the machine gate for visible, audio-responsive mouth motion.

    Direct Avatar capture does not include the browser's playback lead, so its
    relative correlation offset is useful diagnostics but is not an end-user
    A/V-sync measurement.  This gate deliberately checks only what the capture
    can prove: voiced audio changes the lower face and the stream is neither
    black nor frozen.
    """

    gates = report["gates"]
    freeze_ok = gates.get("no_sustained_freeze", gates.get("no_frozen_frames", False))
    return bool(
        gates["mouth_responds_during_voice"]
        and gates["no_black_frames"]
        and freeze_ok
        and gates.get("post_speech_mouth_settles", True)
        and gates.get("post_speech_jitter_not_above_voice", True)
    )


def analyze(args: argparse.Namespace) -> dict:
    rows = list(csv.DictReader((args.capture / "video-timeline.csv").open(encoding="utf-8")))
    sequences = [int(row["sequence"]) for row in rows]
    motion, visual, temporal = generated_delta(
        args.capture / "lipsync-review.mp4", args.dataset, sequences
    )
    energy = audio_energy(args.wav, len(motion))
    usable = min(len(motion), len(energy))
    motion, energy = motion[:usable], energy[:usable]
    search = {offset: correlation_at_shift(energy, motion, round(offset / 40)) for offset in range(-400, 401, 40)}
    best_offset = max(search, key=search.get)
    controls = {offset: correlation_at_shift(energy, motion, round(offset / 40)) for offset in (-400, -200, 0, 200, 400)}
    voiced = energy > max(0.002, float(np.percentile(energy, 35)))
    voiced_motion = float(motion[voiced].mean()) if np.any(voiced) else 0.0
    silent_motion = float(motion[~voiced].mean()) if np.any(~voiced) else 0.0
    manifest_path = args.dataset / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    temporal_resample = str(manifest.get("temporal_resample", "none"))
    source_fps = float(manifest.get("source_fps", 25.0))
    runtime_fps = float(manifest.get("runtime_fps", 25.0))
    playback_rate = 1.0 if temporal_resample != "none" else runtime_fps / source_fps
    tail = post_speech_metrics(
        energy,
        motion,
        temporal["mouth_second_order_motion"],
    )
    voiced_freeze_run = max_consecutive_voiced_freeze(
        energy, temporal["mouth_frame_motion"]
    )
    visual["max_consecutive_voiced_frozen_pairs"] = voiced_freeze_run
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
        "post_speech": tail,
        "dataset_timing": {
            "source_fps": source_fps,
            "runtime_fps": runtime_fps,
            "frame_count": int(manifest.get("frame_count", len(sequences))),
            "temporal_resample": temporal_resample,
            "effective_source_playback_rate": round(playback_rate, 6),
            "blend_profile": str(manifest.get("blend_profile", "lower")),
        },
        "gates": {
            "best_offset_within_80ms": abs(best_offset) <= 80,
            "zero_beats_200ms_controls": controls[0] >= max(controls[-200], controls[200]),
            "zero_beats_400ms_controls": controls[0] >= max(controls[-400], controls[400]),
            "mouth_responds_during_voice": voiced_motion > silent_motion * 1.10,
            "no_black_frames": visual["black_frames"] == 0,
            "no_frozen_frames": visual["frozen_pairs"] == 0,
            "no_sustained_freeze": (
                voiced_freeze_run <= 2
            ),
            "post_speech_mouth_settles": bool(
                tail.get("evaluable") and tail.get("mouth_delta_ratio", math.inf) <= 0.78
            ),
            "post_speech_jitter_not_above_voice": bool(
                tail.get("evaluable") and tail.get("second_order_ratio", math.inf) <= 1.0
            ),
        },
        "limitations": [
            "This is not the unpublished Wav2Lip evaluation SyncNet.",
            "Direct Avatar capture excludes the browser playback lead and cannot sign end-user A/V offset.",
            "Automated motion correlation cannot replace human phoneme/naturalness review.",
            "The post-speech gate requires at least 400 ms of measurable trailing silence.",
        ],
    }
    report["mouth_motion_pass"] = mouth_motion_pass(report)
    report["automated_pass"] = all(
        value for key, value in report["gates"].items() if key != "no_frozen_frames"
    )
    (args.capture / "analysis-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="exit 2 when any automated lip-response gate fails",
    )
    parser.add_argument(
        "--require-mouth-motion",
        action="store_true",
        help="exit 3 unless voiced audio produces visible, non-black, non-frozen mouth motion",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    result = analyze(arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if arguments.require_pass and not result["automated_pass"]:
        raise SystemExit(2)
    if arguments.require_mouth_motion and not result["mouth_motion_pass"]:
        raise SystemExit(3)
