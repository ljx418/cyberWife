"""Build a Wav2Lip Avatar dataset from an approved closed-mouth idle video."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import shutil
import tempfile
from pathlib import Path

import cv2
import numpy as np

try:
    from ops.scrfd_detector import detect_faces
except ModuleNotFoundError:
    from scrfd_detector import detect_faces


# The bundled model is the project's high-resolution ``wav2lip_v2`` network.
# Its encoder/decoder topology and checkpoint require 256px face tensors (the
# original 96px Wav2Lip default is not compatible with this runtime).
WAV2LIP_FACE_SIZE = 256
AVATAR_BUILD_REVISION = "cropv2"
SCENE_AVATAR_BUILD_REVISION = "scenev1"
SMOOTH_SCENE_AVATAR_BUILD_REVISION = "scenev2"


def _resample_frames_and_boxes(
    frames: list[np.ndarray],
    boxes: np.ndarray,
    source_fps: float,
    target_fps: float,
) -> tuple[list[np.ndarray], np.ndarray]:
    """Sample the complete source duration on the runtime frame clock.

    Linear interpolation is intentional for the low-motion approved idles: it
    removes the 16->25fps speed-up without introducing a new optical-flow
    model or a runtime dependency.  Geometry follows the same time weights.
    """
    if source_fps <= 0 or target_fps <= 0 or not frames:
        raise ValueError("source/target fps and frames must be positive")
    duration = len(frames) / source_fps
    count = round(duration * target_fps)
    sampled_frames: list[np.ndarray] = []
    sampled_boxes: list[np.ndarray] = []
    for target_index in range(count):
        position = target_index * source_fps / target_fps
        left = min(int(np.floor(position)), len(frames) - 1)
        right = min(left + 1, len(frames) - 1)
        alpha = float(position - left)
        if left == right or alpha < 1e-9:
            sampled_frames.append(frames[left].copy())
        else:
            sampled_frames.append(cv2.addWeighted(frames[left], 1.0 - alpha, frames[right], alpha, 0))
        sampled_boxes.append(boxes[left] * (1.0 - alpha) + boxes[right] * alpha)
    return sampled_frames, np.rint(np.asarray(sampled_boxes)).astype(np.int32)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _letterbox(frame: np.ndarray, width: int = 512, height: int = 768) -> np.ndarray:
    scale = min(width / frame.shape[1], height / frame.shape[0])
    resized = cv2.resize(frame, (round(frame.shape[1] * scale), round(frame.shape[0] * scale)))
    canvas = np.full((height, width, 3), 24, dtype=np.uint8)
    x = (width - resized.shape[1]) // 2
    y = (height - resized.shape[0]) // 2
    canvas[y:y + resized.shape[0], x:x + resized.shape[1]] = resized
    return canvas


def _smooth(boxes: np.ndarray, radius: int = 2) -> np.ndarray:
    result = boxes.astype(np.float32).copy()
    for index in range(len(boxes)):
        lo, hi = max(0, index - radius), min(len(boxes), index + radius + 1)
        result[index] = np.median(boxes[lo:hi], axis=0)
    return np.rint(result).astype(np.int32)


def _wav2lip_box(
    face: tuple[float, float, float, float],
    *,
    frame_width: int = 512,
    frame_height: int = 768,
) -> list[int]:
    """Return the crop convention used by the bundled Wav2Lip generator.

    The detected crop remains rectangular: it is resized to 256px for model
    input and restored to the detected rectangle afterwards.  Keep the
    detector's sides/top and add only 10px of chin context, matching
    ``avatars/wav2lip/genavatar.py``'s ``pads=[0, 10, 0, 0]`` contract.
    """
    x1, y1, x2, y2 = map(float, face)
    return [
        max(0, round(y1)),
        min(frame_height, round(y2) + 10),
        max(0, round(x1)),
        min(frame_width, round(x2)),
    ]


def _mae(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(np.abs(left.astype(np.float32) - right.astype(np.float32))))


def _loop_metrics(frames: list[np.ndarray]) -> dict[str, float | str]:
    first_last = _mae(frames[0], frames[-1])
    midpoint = len(frames) // 2
    turnaround = _mae(frames[midpoint - 1], frames[midpoint])
    mirrored = [_mae(frames[index], frames[-index - 1]) for index in range(midpoint)]
    palindrome = float(np.mean(mirrored)) if mirrored else 0.0
    mode = "closed_palindrome" if first_last <= 3.0 and palindrome <= 3.0 else "ping_pong"
    return {
        "mode": mode,
        "first_last_mae": round(first_last, 4),
        "turnaround_mae": round(turnaround, 4),
        "palindrome_mae": round(palindrome, 4),
    }


def _validated_loop_mode(
    duration: float,
    metrics: dict[str, float | str],
    *,
    preserve_frame: bool,
) -> str:
    if duration <= 7:
        return str(metrics["mode"])
    if preserve_frame:
        if (
            float(metrics["first_last_mae"]) > 3.0
            or float(metrics["turnaround_mae"]) > 3.0
        ):
            raise RuntimeError(f"complete-scene idle has a visible loop seam: {metrics}")
        return "closed_complete_scene"
    if metrics["mode"] != "closed_palindrome":
        raise RuntimeError(f"long idle video is not a closed palindrome: {metrics}")
    return str(metrics["mode"])


def _idle_motion_metrics(
    boxes: np.ndarray,
    *,
    frame_width: int = 512,
    frame_height: int = 768,
) -> dict[str, float]:
    """Measure face translation/scale without pretending to score naturalness."""
    values = boxes.astype(np.float32)
    centers_x = (values[:, 2] + values[:, 3]) / 2
    centers_y = (values[:, 0] + values[:, 1]) / 2
    median_x, median_y = np.median(centers_x), np.median(centers_y)
    diagonal = float(np.hypot(frame_width, frame_height))
    displacement = np.hypot(centers_x - median_x, centers_y - median_y) / diagonal * 100
    areas = np.maximum(1.0, values[:, 1] - values[:, 0]) * np.maximum(
        1.0, values[:, 3] - values[:, 2]
    )
    return {
        "face_center_p95_percent_diagonal": round(float(np.percentile(displacement, 95)), 4),
        "face_area_cv_percent": round(float(np.std(areas) / np.mean(areas) * 100), 4),
    }


def build(
    source_portrait: Path,
    idle_video: Path,
    output_root: Path,
    avatar_id: str,
    *,
    preserve_frame: bool = False,
    target_fps: float | None = None,
    blend_profile: str = "lower",
) -> Path:
    if not source_portrait.is_file() or not idle_video.is_file():
        raise FileNotFoundError("source portrait or idle video is missing")
    if blend_profile not in {"lower", "mouth_oval_v1", "full"}:
        raise ValueError(f"unsupported blend profile: {blend_profile}")
    model_path = Path(os.environ.get(
        "CW_FACE_DETECTOR_ONNX",
        "/mnt/c/ComfyUI-aki-v2/ComfyUI/models/insightface/models/buffalo_l/det_10g.onnx",
    ))
    if not model_path.is_file():
        raise FileNotFoundError(f"offline SCRFD model missing: {model_path}")
    capture = cv2.VideoCapture(str(idle_video))
    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frames: list[np.ndarray] = []
    raw_boxes: list[list[int]] = []
    frame_width = 0
    frame_height = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        canvas = frame if preserve_frame else _letterbox(frame)
        if not frames:
            frame_height, frame_width = canvas.shape[:2]
        elif canvas.shape[:2] != (frame_height, frame_width):
            raise RuntimeError("idle video frame size changed within stream")
        faces = detect_faces(canvas, model_path)
        if len(faces) != 1:
            raise RuntimeError(f"frame {len(frames)} expected one face, found {len(faces)}")
        x1, y1, x2, y2, _ = faces[0]
        raw_boxes.append(_wav2lip_box(
            (x1, y1, x2, y2),
            frame_width=frame_width,
            frame_height=frame_height,
        ))
        frames.append(canvas)
    capture.release()
    duration = len(frames) / source_fps if source_fps else 0
    if not 4 <= duration <= 10.5 or not 12 <= source_fps <= 30:
        raise RuntimeError(
            f"idle video outside 4-10.5s contract: frames={len(frames)}, "
            f"fps={source_fps:.3f}, duration={duration:.3f}"
        )
    loop_metrics = _loop_metrics(frames)
    loop_metrics["mode"] = _validated_loop_mode(
        duration, loop_metrics, preserve_frame=preserve_frame,
    )

    boxes = _smooth(np.asarray(raw_boxes))
    if np.max(np.abs(np.diff(boxes, axis=0))) > 48:
        raise RuntimeError("face box discontinuity exceeds 48 pixels")
    motion_metrics = _idle_motion_metrics(
        boxes,
        frame_width=frame_width,
        frame_height=frame_height,
    )
    if (
        motion_metrics["face_center_p95_percent_diagonal"] > 2.5
        or motion_metrics["face_area_cv_percent"] > 3.0
    ):
        raise RuntimeError(f"idle motion exceeds low-motion gate: {motion_metrics}")
    source_frame_count = len(frames)
    if target_fps is not None:
        if not 12 <= target_fps <= 30:
            raise ValueError("target_fps must be within 12-30")
        frames, boxes = _resample_frames_and_boxes(
            frames, boxes.astype(np.float32), source_fps, target_fps,
        )
    runtime_fps = float(target_fps or source_fps)
    target = output_root / avatar_id
    if target.exists():
        raise FileExistsError(f"target exists; refusing overwrite: {target}")
    output_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{avatar_id}-", dir=output_root))
    try:
        full_dir, face_dir = temporary / "full_imgs", temporary / "face_imgs"
        full_dir.mkdir(); face_dir.mkdir()
        coords: list[tuple[int, int, int, int]] = []
        for index, (frame, box) in enumerate(zip(frames, boxes)):
            y1, y2, x1, x2 = map(int, box)
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                raise RuntimeError(f"empty face crop at frame {index}")
            face = cv2.resize(
                crop,
                (WAV2LIP_FACE_SIZE, WAV2LIP_FACE_SIZE),
                interpolation=cv2.INTER_AREA,
            )
            if not cv2.imwrite(str(full_dir / f"{index:08d}.png"), frame):
                raise RuntimeError("failed to write full frame")
            if not cv2.imwrite(str(face_dir / f"{index:08d}.png"), face):
                raise RuntimeError("failed to write face frame")
            coords.append((y1, y2, x1, x2))
        if len(coords) != len(frames):
            raise RuntimeError("avatar frame/coordinate count mismatch")
        with (temporary / "coords.pkl").open("wb") as stream:
            pickle.dump(coords, stream)
        median_box = np.median(boxes, axis=0).astype(int).tolist()
        manifest = {
            "schema": 2,
            "build_revision": (
                SMOOTH_SCENE_AVATAR_BUILD_REVISION
                if preserve_frame and target_fps is not None
                else SCENE_AVATAR_BUILD_REVISION if preserve_frame
                else AVATAR_BUILD_REVISION
            ),
            "avatar_id": avatar_id,
            "source_sha256": _sha256(source_portrait),
            "idle_video_sha256": _sha256(idle_video),
            "frame_size": [frame_width, frame_height],
            "presentation": "complete_scene" if preserve_frame else "portrait",
            "face_size": [WAV2LIP_FACE_SIZE, WAV2LIP_FACE_SIZE],
            "coordinates": median_box,
            "frame_count": len(frames),
            "source_fps": round(source_fps, 3),
            "source_frame_count": source_frame_count,
            "runtime_fps": round(runtime_fps, 3),
            "temporal_resample": "linear" if target_fps is not None else "none",
            "blend_profile": blend_profile,
            "duration_seconds": round(duration, 3),
            "loop_mode": loop_metrics["mode"],
            "loop_seam": {
                key: value for key, value in loop_metrics.items() if key != "mode"
            },
            "idle_motion": motion_metrics,
            "face_detector": "scrfd",
            "visual_approval_required": True,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, target)
        return target
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--avatar-id", required=True)
    parser.add_argument(
        "--preserve-frame",
        action="store_true",
        help="retain the complete generated scene as the speaking surface",
    )
    parser.add_argument("--target-fps", type=float)
    parser.add_argument(
        "--blend-profile",
        choices=("lower", "mouth_oval_v1", "full"),
        default="lower",
    )
    args = parser.parse_args()
    print(build(
        args.source,
        args.video,
        args.output_root,
        args.avatar_id,
        preserve_frame=args.preserve_frame,
        target_fps=args.target_fps,
        blend_profile=args.blend_profile,
    ))


if __name__ == "__main__":
    main()
