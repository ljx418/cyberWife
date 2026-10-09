#!/usr/bin/env python3
"""Build non-active MuseTalk candidates for a three-scene appearance set."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
from argparse import Namespace
from pathlib import Path
from uuid import UUID, uuid5

import torch

from cyberwife.application.scene_preset_service import ScenePresetService
from ops.avatar_idle_pipeline import _component_ready, _launcher
from ops.build_musetalk_avatar import build as build_musetalk
from ops.build_video_avatar import build as build_wav2lip


AVATAR_NAMESPACE = UUID("4e897d73-c648-4724-a79e-3ae4504a13f7")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build(args: argparse.Namespace) -> dict:
    keyframes = json.loads((args.keyframe_dir / "manifest.json").read_text(encoding="utf-8"))
    idles = json.loads((args.idle_dir / "manifest.json").read_text(encoding="utf-8"))
    if keyframes.get("appearance_id") != args.appearance_id:
        raise ValueError("appearance.id_mismatch")
    if idles.get("generation_mode") != "direct_complete_scene" or idles.get("matting") is not False:
        raise ValueError("appearance.idle_manifest_invalid")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stopped: list[str] = []
    records: dict[str, dict] = {}
    try:
        for component in ("avatar", "speech", "llama"):
            if _component_ready(component):
                _launcher("stop", component)
                stopped.append(component)
        for slug in sorted(keyframes["records"]):
            key_record = keyframes["records"][slug]
            idle_record = idles["records"][slug]
            keyframe = Path(key_record["output"]).resolve()
            idle = Path(idle_record["output"]).resolve()
            if sha256(keyframe) != key_record["output_sha256"] or sha256(idle) != idle_record["output_sha256"]:
                raise ValueError(f"appearance.input_hash_mismatch:{slug}")
            token = str(uuid5(
                AVATAR_NAMESPACE,
                f"{args.appearance_id}:{slug}:{sha256(idle)}:coord-median-v1",
            ))[:12]
            wav_id = f"wav2lip256_app_{token}_scenev2_mouth"
            muse_id = f"musetalk15_app_{token}_scenev2_stable"
            wav_target = args.avatar_root / wav_id
            if not wav_target.exists():
                build_wav2lip(
                    keyframe, idle, args.avatar_root, wav_id,
                    preserve_frame=True, target_fps=25.0, blend_profile="mouth_oval_v1",
                )
            muse_target = args.avatar_root / muse_id
            if not muse_target.exists():
                build_musetalk(Namespace(
                    source_dataset=wav_target,
                    output_root=args.avatar_root,
                    avatar_id=muse_id,
                    model_root=args.model_root,
                    extra_margin=0,
                    left_cheek_width=90,
                    right_cheek_width=90,
                    visual_approved=False,
                    coordinate_stabilization="median",
                ))
            muse_manifest = json.loads((muse_target / "manifest.json").read_text(encoding="utf-8"))
            if (
                muse_manifest.get("visual_approved") is not False
                or muse_manifest.get("frame_count") != 250
                or muse_manifest.get("coordinate_stabilization") != "median"
            ):
                raise ValueError(f"appearance.candidate_manifest_invalid:{slug}")
            records[slug] = {
                "scene_id": ScenePresetService.scene_id(slug),
                "appearance_id": args.appearance_id,
                "appearance_label": keyframes.get("appearance_label"),
                "keyframe": str(keyframe),
                "keyframe_sha256": sha256(keyframe),
                "idle": str(idle),
                "idle_sha256": sha256(idle),
                "wav2lip_avatar_id": wav_id,
                "musetalk_avatar_id": muse_id,
                "musetalk_manifest_sha256": sha256(muse_target / "manifest.json"),
                "status": "staged",
            }
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        result = {
            "schema_version": 1,
            "appearance_id": args.appearance_id,
            "appearance_label": keyframes.get("appearance_label"),
            "engine": "musetalk",
            "presentation": "complete_scene",
            "matting": False,
            "visual_approval_required": True,
            "records": records,
        }
        (args.output_dir / "candidate-manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return result
    finally:
        errors: list[str] = []
        for component in reversed(stopped):
            try:
                _launcher("start", component)
            except Exception as exc:
                errors.append(f"{component}:{exc}")
        if errors:
            raise RuntimeError("runtime_restore_failed:" + ",".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--appearance-id", required=True)
    parser.add_argument("--keyframe-dir", required=True, type=Path)
    parser.add_argument("--idle-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--avatar-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    print(json.dumps(build(parser.parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
