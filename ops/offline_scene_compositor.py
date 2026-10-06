#!/usr/bin/env python3
"""Extract a whole-person matte and pre-compose an idle clip into local scenes.

The source contract intentionally uses a uniform #D8D3CC studio background.
This module removes that background from the *complete frame sequence*.  It
never crops, replaces, or synthesizes eyes or other facial regions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from ops.make_seamless_idle import encode, mean_absolute_error, read_frames


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cover(image: np.ndarray, width: int, height: int) -> np.ndarray:
    scale = max(width / image.shape[1], height / image.shape[0])
    resized = cv2.resize(
        image,
        (round(image.shape[1] * scale), round(image.shape[0] * scale)),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
    )
    x = (resized.shape[1] - width) // 2
    y = (resized.shape[0] - height) // 2
    return resized[y:y + height, x:x + width]


def _studio_distance(frame: np.ndarray) -> np.ndarray:
    """Measure distance from the *rendered* studio plate.

    The requested #D8D3CC is a semantic generation target, not a reliable
    decoded pixel value.  Estimate the actual plate from guaranteed-empty top
    corners and side rails so exposure changes do not turn the whole plate
    into foreground.
    """
    height, width = frame.shape[:2]
    top = max(8, round(height * 0.12))
    side = max(8, round(width * 0.08))
    samples = np.concatenate(
        (
            frame[:top, :round(width * 0.18)].reshape(-1, 3),
            frame[:top, -round(width * 0.18):].reshape(-1, 3),
            frame[round(height * 0.15):round(height * 0.62), :side].reshape(-1, 3),
            frame[round(height * 0.15):round(height * 0.62), -side:].reshape(-1, 3),
        )
    )
    reference = np.rint(np.median(samples, axis=0)).astype(np.uint8)
    target = np.full_like(frame, reference, dtype=np.uint8)
    frame_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype(np.float32)
    return np.linalg.norm(frame_lab - target_lab, axis=2)


def whole_person_mattes(frames: list[np.ndarray]) -> list[np.ndarray]:
    """Return temporally stable whole-person alpha mattes in [0, 1]."""
    if not frames:
        raise ValueError("frames cannot be empty")
    height, width = frames[0].shape[:2]
    yy, xx = np.mgrid[:height, :width]
    central_prior = (
        ((xx - width * 0.5) / (width * 0.48)) ** 2
        + ((yy - height * 0.58) / (height * 0.72)) ** 2
    ) <= 1.0
    results: list[np.ndarray] = []
    previous: np.ndarray | None = None
    kernel = np.ones((5, 5), np.uint8)

    for frame in frames:
        if frame.shape[:2] != (height, width):
            raise ValueError("all source frames must share dimensions")
        distance = _studio_distance(frame)
        mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)
        mask[distance < 7.0] = cv2.GC_BGD
        mask[central_prior & (distance >= 9.0)] = cv2.GC_PR_FGD
        mask[central_prior & (distance >= 22.0)] = cv2.GC_FGD

        # Corners and side rails are guaranteed studio background by the
        # frontalization contract.  The lower edge is not: clothing exits it.
        rail = max(3, round(width * 0.018))
        cap = max(3, round(height * 0.012))
        mask[:cap, :] = cv2.GC_BGD
        mask[:, :rail] = cv2.GC_BGD
        mask[:, -rail:] = cv2.GC_BGD
        cv2.grabCut(frame, mask, None, None, None, 3, cv2.GC_INIT_WITH_MASK)
        binary = np.where(
            (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0
        ).astype(np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

        # Keep the connected foreground component crossing the vertical centre.
        count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
        candidates = []
        for label in range(1, count):
            x, y, w, h, area = stats[label]
            if x <= width // 2 < x + w and area >= width * height * 0.04:
                candidates.append((area, label))
        if not candidates:
            raise RuntimeError("whole_person_matte_missing")
        label = max(candidates)[1]
        alpha = (labels == label).astype(np.float32)
        alpha = cv2.GaussianBlur(alpha, (0, 0), 1.25)
        alpha = np.clip(alpha, 0.0, 1.0)
        if previous is not None:
            alpha = previous * 0.28 + alpha * 0.72
        previous = alpha
        results.append(alpha)
    return results


def compose_scenes(
    source_video: Path,
    backgrounds: dict[str, Path],
    output_dir: Path,
) -> dict:
    frames, fps = read_frames(source_video)
    mattes = whole_person_mattes(frames)
    output_dir.mkdir(parents=True, exist_ok=True)
    height, width = frames[0].shape[:2]

    alpha_stack = np.stack(mattes)
    alpha_path = output_dir / "whole-person-alpha.npz"
    np.savez_compressed(alpha_path, alpha=np.rint(alpha_stack * 255).astype(np.uint8))
    outputs: dict[str, dict] = {}
    for scene_id, background_path in backgrounds.items():
        background = cv2.imread(str(background_path), cv2.IMREAD_COLOR)
        if background is None:
            raise RuntimeError(f"background_decode_failed:{background_path}")
        plate = _cover(background, width, height).astype(np.float32)
        composed = []
        for frame, alpha in zip(frames, mattes):
            weight = alpha[..., None]
            merged = frame.astype(np.float32) * weight + plate * (1.0 - weight)
            composed.append(np.rint(merged).clip(0, 255).astype(np.uint8))
        target = output_dir / f"idle-{scene_id}.mp4"
        encode(composed, target, fps=round(fps))
        decoded, decoded_fps = read_frames(target)
        outputs[scene_id] = {
            "path": str(target),
            "sha256": _sha256(target),
            "background_path": str(background_path),
            "background_sha256": _sha256(background_path),
            "frame_count": len(decoded),
            "fps": round(decoded_fps, 3),
            "first_last_mae": round(mean_absolute_error(decoded[0], decoded[-1]), 4),
        }

    areas = np.mean(alpha_stack > 0.5, axis=(1, 2))
    changes = np.mean(np.abs(np.diff(alpha_stack, axis=0)), axis=(1, 2))
    manifest = {
        "schema_version": 1,
        "source_video": str(source_video),
        "source_sha256": _sha256(source_video),
        "matting_scope": "whole_person_full_frame",
        "localized_facial_compositing": False,
        "alpha_path": str(alpha_path),
        "alpha_sha256": _sha256(alpha_path),
        "frame_size": [width, height],
        "frame_count": len(frames),
        "fps": round(fps, 3),
        "mask_area_mean_percent": round(float(np.mean(areas) * 100), 4),
        "mask_area_cv_percent": round(float(np.std(areas) / np.mean(areas) * 100), 4),
        "mask_temporal_delta_p95_percent": round(float(np.percentile(changes, 95) * 100), 4),
        "outputs": outputs,
    }
    (output_dir / "scene-composite-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--background-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    backgrounds = {
        path.stem: path for path in sorted(args.background_dir.glob("*.webp"))
    }
    if not backgrounds:
        raise RuntimeError("no_backgrounds_found")
    print(json.dumps(
        compose_scenes(args.video, backgrounds, args.output_dir),
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
