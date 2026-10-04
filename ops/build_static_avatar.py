"""Build a private LiveTalking/Wav2Lip avatar dataset from one portrait."""
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
except ModuleNotFoundError:  # direct ``python ops/build_static_avatar.py``
    from scrfd_detector import detect_faces


def build(source: Path, output_root: Path, avatar_id: str) -> Path:
    if not source.is_file():
        raise FileNotFoundError(source)
    target = output_root / avatar_id
    required = (target / "coords.pkl", target / "full_imgs" / "00000000.png", target / "face_imgs" / "00000000.png")
    if all(path.is_file() for path in required):
        return target
    output_root.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=f".{avatar_id}-", dir=output_root))
    try:
        full_dir = tmp / "full_imgs"
        face_dir = tmp / "face_imgs"
        full_dir.mkdir()
        face_dir.mkdir()
        original = cv2.imread(str(source), cv2.IMREAD_UNCHANGED)
        if original is None:
            raise ValueError("portrait could not be decoded")
        if original.ndim == 3 and original.shape[2] == 4:
            alpha = original[:, :, 3:4].astype(np.float32) / 255.0
            rgb = original[:, :, :3].astype(np.float32)
            background = np.full_like(rgb, 24.0)
            original = (rgb * alpha + background * (1.0 - alpha)).astype(np.uint8)
        height, width = original.shape[:2]
        scale = min(512 / width, 768 / height)
        resized = cv2.resize(original, (max(1, int(width * scale)), max(1, int(height * scale))))
        canvas = np.full((768, 512, 3), 24, dtype=np.uint8)
        xoff = (512 - resized.shape[1]) // 2
        yoff = (768 - resized.shape[0]) // 2
        canvas[yoff:yoff + resized.shape[0], xoff:xoff + resized.shape[1]] = resized

        gray = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
        bundled = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade_path = Path(os.environ.get(
            "CW_FACE_CASCADE",
            bundled if bundled.is_file() else Path.home() / ".cyberWife" / "models" / "face_detection" / "haarcascade_frontalface_default.xml",
        ))
        if not cascade_path.is_file():
            raise FileNotFoundError(f"offline face cascade missing: {cascade_path}")
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            raise RuntimeError(f"face cascade could not be loaded: {cascade_path}")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(96, 96))
        detector = "haar"
        if len(faces) == 1:
            x, y, w, h = [int(value) for value in faces[0]]
        else:
            scrfd_path = Path(os.environ.get(
                "CW_FACE_DETECTOR_ONNX",
                "/mnt/c/ComfyUI-aki-v2/ComfyUI/models/insightface/models/buffalo_l/det_10g.onnx",
            ))
            if not scrfd_path.is_file():
                raise RuntimeError(
                    f"expected exactly one frontal face, found {len(faces)}; offline SCRFD model missing"
                )
            robust_faces = detect_faces(canvas, scrfd_path)
            if len(robust_faces) != 1:
                raise RuntimeError(f"expected exactly one face, found {len(robust_faces)}")
            x1d, y1d, x2d, y2d, _ = robust_faces[0]
            x, y = int(x1d), int(y1d)
            w, h = int(x2d - x1d), int(y2d - y1d)
            detector = "scrfd"
        pad_x = int(w * 0.18)
        pad_top = int(h * 0.20)
        pad_bottom = int(h * 0.32)
        x1, x2 = max(0, x - pad_x), min(canvas.shape[1], x + w + pad_x)
        y1, y2 = max(0, y - pad_top), min(canvas.shape[0], y + h + pad_bottom)
        crop = canvas[y1:y2, x1:x2]
        if crop.size == 0:
            raise RuntimeError("detected face crop is empty")
        face = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_AREA)
        if not cv2.imwrite(str(full_dir / "00000000.png"), canvas):
            raise RuntimeError("failed to write full frame")
        if not cv2.imwrite(str(face_dir / "00000000.png"), face):
            raise RuntimeError("failed to write face frame")
        with (tmp / "coords.pkl").open("wb") as stream:
            pickle.dump([(y1, y2, x1, x2)], stream)
        sha = hashlib.sha256(source.read_bytes()).hexdigest()
        (tmp / "manifest.json").write_text(json.dumps({
            "schema": 1,
            "avatar_id": avatar_id,
            "source_sha256": sha,
            "frame_size": [512, 768],
            "face_size": [256, 256],
            "coordinates": [y1, y2, x1, x2],
            "frame_count": 1,
            "face_detector": detector,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        if target.exists():
            raise FileExistsError(f"incomplete target exists; refusing to overwrite: {target}")
        os.replace(tmp, target)
        return target
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--avatar-id", default="wav2lip256_avatar1")
    args = parser.parse_args()
    print(build(args.source, args.output_root, args.avatar_id))


if __name__ == "__main__":
    main()
