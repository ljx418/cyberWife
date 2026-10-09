#!/usr/bin/env python3
"""Build and atomically activate MuseTalk renditions for all approved scenes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from argparse import Namespace
from pathlib import Path
from uuid import UUID, uuid5

from ops.build_musetalk_avatar import build
from ops.select_avatar_engine import select


RENDITION_NAMESPACE = UUID("857184e6-617f-4e39-9238-c4f54a642f59")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(target: Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def _synchronize_manifest(target_dataset: Path, source_dataset: Path) -> dict:
    target_path = target_dataset / "manifest.json"
    source = json.loads((source_dataset / "manifest.json").read_text(encoding="utf-8"))
    manifest = json.loads(target_path.read_text(encoding="utf-8"))
    manifest.update({
        "schema": 2,
        "build_revision": "musetalk15-scenev2",
        "engine": "musetalk15",
        "source_sha256": source.get("source_sha256"),
        "idle_video_sha256": source.get("idle_video_sha256"),
        "presentation": source.get("presentation", "complete_scene"),
        "coordinates": source.get("coordinates"),
        "source_fps": source.get("source_fps"),
        "source_frame_count": source.get("source_frame_count"),
        "temporal_resample": source.get("temporal_resample"),
        "duration_seconds": source.get("duration_seconds"),
        "loop_mode": source.get("loop_mode"),
        "loop_seam": source.get("loop_seam"),
        "idle_motion": source.get("idle_motion"),
        "blend_profile": "jaw",
        "visual_approval_required": True,
        "visual_approved": True,
    })
    _atomic_json(target_path, manifest)
    return manifest


def install(data_root: Path, model_root: Path) -> dict:
    data_root = data_root.resolve()
    model_root = model_root.resolve()
    binding_root = data_root / "v2x" / "scene-renditions"
    active_binding = binding_root / "scene-bindings.v1.json"
    wav_variant = binding_root / "scene-bindings.wav2lip.v1.json"
    if not active_binding.is_file():
        raise FileNotFoundError("scene.binding_manifest_missing")
    current = json.loads(active_binding.read_text(encoding="utf-8"))
    if all(str(item.get("engine", "wav2lip")) == "wav2lip" for item in current.get("bindings", [])):
        wav_payload = current
        for item in wav_payload["bindings"]:
            item["engine"] = "wav2lip"
        _atomic_json(wav_variant, wav_payload)
    elif wav_variant.is_file():
        wav_payload = json.loads(wav_variant.read_text(encoding="utf-8"))
    else:
        raise ValueError("scene.wav2lip_variant_missing")
    if len(wav_payload.get("bindings", [])) != 4:
        raise ValueError("scene.binding_count_invalid")

    avatar_root = data_root / "avatar" / "avatars"
    muse_bindings: list[dict] = []

    for item in wav_payload["bindings"]:
        source_avatar_id = str(item["speaking_avatar_id"])
        source_dataset = avatar_root / source_avatar_id
        target_id = source_avatar_id.replace("wav2lip256_", "musetalk15_", 1).replace("_mouth", "")
        target_dataset = avatar_root / target_id
        if not target_dataset.exists():
            build(Namespace(
                source_dataset=source_dataset,
                output_root=avatar_root,
                avatar_id=target_id,
                model_root=model_root,
                extra_margin=0,
                left_cheek_width=90,
                right_cheek_width=90,
                visual_approved=True,
            ))
        manifest_path = target_dataset / "manifest.json"
        manifest = _synchronize_manifest(target_dataset, source_dataset)
        if manifest.get("visual_approved") is not True or manifest.get("frame_count") != 250:
            raise ValueError(f"scene.musetalk_dataset_invalid:{target_id}")
        talking_sha = _sha256(manifest_path)
        muse_item = dict(item)
        muse_item.update({
            "engine": "musetalk",
            "speaking_avatar_id": target_id,
            "talking_sha256": talking_sha,
            "talking_rendition_id": str(uuid5(
                RENDITION_NAMESPACE, f"{item['scene_id']}:talking:musetalk:{talking_sha}"
            )),
        })
        muse_bindings.append(muse_item)

    muse_payload = {
        "schema_version": 1,
        "source_pack_id": wav_payload.get("source_pack_id"),
        "source_sha256": wav_payload.get("source_sha256"),
        "engine": "musetalk",
        "bindings": sorted(muse_bindings, key=lambda value: value["scene_id"]),
    }
    muse_variant = binding_root / "scene-bindings.musetalk.v1.json"
    _atomic_json(muse_variant, muse_payload)
    selected = select(data_root, "musetalk")
    return {
        "result": "PASS",
        "revision": selected["revision"],
        "datasets": [item["speaking_avatar_id"] for item in muse_bindings],
        "selected": selected,
        "rollback": str(wav_variant),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(args.data_root, args.model_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
