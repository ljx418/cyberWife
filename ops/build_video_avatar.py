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


def build(source_portrait: Path, idle_video: Path, output_root: Path, avatar_id: str) -> Path:
    if not source_portrait.is_file() or not idle_video.is_file():
        raise FileNotFoundError("source portrait or idle video is missing")
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
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        canvas = _letterbox(frame)
        faces = detect_faces(canvas, model_path)
        if len(faces) != 1:
            raise RuntimeError(f"frame {len(frames)} expected one face, found {len(faces)}")
        x1, y1, x2, y2, _ = faces[0]
        width, height = x2 - x1, y2 - y1
        raw_boxes.append([
            max(0, int(y1 - height * 0.20)), min(768, int(y2 + height * 0.32)),
            max(0, int(x1 - width * 0.18)), min(512, int(x2 + width * 0.18)),
        ])
        frames.append(canvas)
    capture.release()
    if not 64 <= len(frames) <= 120 or not 12 <= source_fps <= 30:
        raise RuntimeError(f"idle video outside 4-7s contract: frames={len(frames)}, fps={source_fps:.3f}")

    boxes = _smooth(np.asarray(raw_boxes))
    if np.max(np.abs(np.diff(boxes, axis=0))) > 48:
        raise RuntimeError("face box discontinuity exceeds 48 pixels")
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
            face = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)
            if not cv2.imwrite(str(full_dir / f"{index:08d}.png"), frame):
                raise RuntimeError("failed to write full frame")
            if not cv2.imwrite(str(face_dir / f"{index:08d}.png"), face):
                raise RuntimeError("failed to write face frame")
            coords.append((y1, y2, x1, x2))
        with (temporary / "coords.pkl").open("wb") as stream:
            pickle.dump(coords, stream)
        median_box = np.median(boxes, axis=0).astype(int).tolist()
        manifest = {
            "schema": 2,
            "avatar_id": avatar_id,
            "source_sha256": _sha256(source_portrait),
            "idle_video_sha256": _sha256(idle_video),
            "frame_size": [512, 768],
            "face_size": [256, 256],
            "coordinates": median_box,
            "frame_count": len(frames),
            "source_fps": round(source_fps, 3),
            "loop_mode": "ping_pong",
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
    args = parser.parse_args()
    print(build(args.source, args.video, args.output_root, args.avatar_id))


if __name__ == "__main__":
    main()
