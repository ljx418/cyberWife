"""Build a MuseTalk 1.5 canary from an approved complete-scene dataset.

The builder deliberately reuses the already-audited face coordinates instead
of detecting a new identity/face box.  That keeps Wav2Lip and MuseTalk A/B
captures on the same source frames and crop geometry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
from pathlib import Path

import cv2
import numpy as np
import torch


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numbered_images(path: Path) -> list[Path]:
    return sorted(path.glob("*.png"), key=lambda item: int(item.stem))


def stabilize_coordinates(coordinates: list, mode: str) -> list[list[int]]:
    values = np.asarray(coordinates, dtype=np.float32)
    if values.ndim != 2 or values.shape[1] != 4 or len(values) == 0:
        raise ValueError("invalid source face coordinates")
    if mode == "source":
        return np.rint(values).astype(int).tolist()
    if mode != "median":
        raise ValueError(f"unsupported coordinate stabilization: {mode}")
    median = np.rint(np.median(values, axis=0)).astype(int).tolist()
    return [list(median) for _ in range(len(values))]


def build(args: argparse.Namespace) -> dict:
    source = args.source_dataset.resolve()
    output_root = args.output_root.resolve()
    target = output_root / args.avatar_id
    if target.exists():
        raise FileExistsError(f"refusing to overwrite MuseTalk dataset: {target}")

    source_images = numbered_images(source / "full_imgs")
    source_coords = pickle.loads((source / "coords.pkl").read_bytes())
    if not source_images or len(source_images) != len(source_coords):
        raise ValueError("source images and coordinates must be non-empty and aligned")

    os.environ["CW_MUSETALK_MODEL_ROOT"] = str(args.model_root.resolve())
    from workers.avatar.avatars.musetalk.models.vae import VAE
    from workers.avatar.avatars.musetalk.utils.blending import get_image_prepare_material
    from workers.avatar.avatars.musetalk.utils.face_parsing import FaceParsing

    coordinate_stabilization = str(getattr(args, "coordinate_stabilization", "source"))
    source_coords = stabilize_coordinates(source_coords, coordinate_stabilization)
    target.mkdir(parents=True)
    full_images = target / "full_imgs"
    masks = target / "mask"
    full_images.mkdir()
    masks.mkdir()

    vae = VAE(model_path=str(args.model_root / "sd-vae"), use_float16=True)
    parser = FaceParsing(
        left_cheek_width=args.left_cheek_width,
        right_cheek_width=args.right_cheek_width,
    )
    muse_coords: list[list[int]] = []
    mask_coords: list[list[int]] = []
    latents: list[torch.Tensor] = []

    for index, (image_path, wav_box) in enumerate(zip(source_images, source_coords)):
        frame = cv2.imread(str(image_path))
        if frame is None:
            raise ValueError(f"unable to read source frame: {image_path}")
        y1, y2, x1, x2 = (int(value) for value in wav_box)
        y2 = min(frame.shape[0], y2 + args.extra_margin)
        if min(x1, y1) < 0 or x2 <= x1 or y2 <= y1:
            raise ValueError(f"invalid source face box at frame {index}: {wav_box}")
        face_box = [x1, y1, x2, y2]
        crop = frame[y1:y2, x1:x2]
        crop = cv2.resize(crop, (256, 256), interpolation=cv2.INTER_LANCZOS4)
        latents.append(vae.get_latents_for_unet(crop).detach().cpu())
        mask, mask_box = get_image_prepare_material(
            frame, face_box, fp=parser, mode="jaw",
        )
        if mask_box[0] < 0 or mask_box[1] < 0 or mask_box[2] > frame.shape[1] or mask_box[3] > frame.shape[0]:
            raise ValueError(f"expanded mask box escapes frame at {index}: {mask_box}")
        os.link(image_path, full_images / f"{index:08d}.png")
        if not cv2.imwrite(str(masks / f"{index:08d}.png"), mask):
            raise OSError(f"unable to write mask for frame {index}")
        muse_coords.append(face_box)
        mask_coords.append([int(value) for value in mask_box])
        if index % 25 == 0 or index + 1 == len(source_images):
            print(f"prepared {index + 1}/{len(source_images)} frames", flush=True)

    (target / "coords.pkl").write_bytes(pickle.dumps(muse_coords))
    (target / "mask_coords.pkl").write_bytes(pickle.dumps(mask_coords))
    torch.save(latents, target / "latents.pt")
    (target / "avator_info.json").write_text(
        json.dumps({
            "avatar_id": args.avatar_id,
            "engine": "musetalk15",
            "source_dataset": source.name,
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    source_manifest_path = source / "manifest.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    manifest = {
        "schema": 2,
        "build_revision": "musetalk15-scenev2",
        "avatar_id": args.avatar_id,
        "engine": "musetalk15",
        "source_avatar_id": source_manifest.get("avatar_id", source.name),
        "source_manifest_sha256": sha256(source_manifest_path),
        "source_sha256": source_manifest.get("source_sha256"),
        "idle_video_sha256": source_manifest.get("idle_video_sha256"),
        "frame_count": len(source_images),
        "frame_size": source_manifest.get("frame_size"),
        "presentation": source_manifest.get("presentation", "complete_scene"),
        "coordinates": source_manifest.get("coordinates"),
        "source_fps": source_manifest.get("source_fps"),
        "source_frame_count": source_manifest.get("source_frame_count"),
        "temporal_resample": source_manifest.get("temporal_resample"),
        "duration_seconds": source_manifest.get("duration_seconds"),
        "loop_mode": source_manifest.get("loop_mode"),
        "loop_seam": source_manifest.get("loop_seam"),
        "idle_motion": source_manifest.get("idle_motion"),
        "runtime_fps": 25.0,
        "face_size": [256, 256],
        "face_box_source": (
            "approved_wav2lip_dataset_median"
            if coordinate_stabilization == "median"
            else "approved_wav2lip_dataset"
        ),
        "coordinate_stabilization": coordinate_stabilization,
        "parsing_mode": "jaw",
        "blend_profile": "jaw",
        "extra_margin": args.extra_margin,
        "model_sha256": {
            "musetalk15_unet": sha256(args.model_root / "musetalkV15" / "unet.pth"),
            "sd_vae": sha256(args.model_root / "sd-vae" / "diffusion_pytorch_model.bin"),
            "whisper_tiny": sha256(args.model_root / "whisper" / "pytorch_model.bin"),
            "face_parse": sha256(args.model_root / "face-parse-bisent" / "79999_iter.pth"),
        },
        "active": False,
        "visual_approval_required": True,
        "visual_approved": bool(args.visual_approved),
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dataset", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--avatar-id", required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--extra-margin", type=int, default=0)
    parser.add_argument("--left-cheek-width", type=int, default=90)
    parser.add_argument("--right-cheek-width", type=int, default=90)
    parser.add_argument("--visual-approved", action="store_true")
    parser.add_argument(
        "--coordinate-stabilization", choices=("source", "median"), default="source"
    )
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(build(parse_args()), ensure_ascii=False, indent=2))
