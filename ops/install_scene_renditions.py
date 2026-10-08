#!/usr/bin/env python3
"""Install human-approved complete-scene Idle/talking pairs into private V2-X state."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import UUID, uuid5

from cyberwife.application.scene_preset_service import DEFAULT_SCENES, ScenePresetService
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository
from ops.build_video_avatar import SCENE_AVATAR_BUILD_REVISION, build


RENDITION_NAMESPACE = UUID("857184e6-617f-4e39-9238-c4f54a642f59")
GENERATED_SCENES = {"garden-sunroom", "morning-bedroom", "rainy-library"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def _approve_avatar_manifest(target: Path, *, source_sha: str, idle_sha: str) -> dict:
    manifest_path = target / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        payload.get("source_sha256") != source_sha
        or payload.get("idle_video_sha256") != idle_sha
        or payload.get("presentation") != "complete_scene"
        or payload.get("frame_count") != 160
    ):
        raise RuntimeError(f"scene.avatar_manifest_mismatch:{target.name}")
    if payload.get("visual_approved") is not True:
        payload["visual_approved"] = True
        temporary = manifest_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(temporary, manifest_path)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def install(
    *,
    data_root: Path,
    assets_root: Path,
    backgrounds_root: Path,
    generated_manifest_path: Path,
    default_job_path: Path,
) -> dict:
    data_root = data_root.resolve()
    binding_root = data_root / "v2x" / "scene-renditions"
    avatar_root = data_root / "avatar" / "avatars"
    repository = JsonManifestRepository(data_root)
    source_pack = SourcePackService(repository)
    scenes = ScenePresetService(source_pack, backgrounds_root)
    scenes.ensure_registered()
    manifest = source_pack.load()
    if manifest is None:
        raise RuntimeError("source_pack.required")

    generated = json.loads(generated_manifest_path.read_text(encoding="utf-8"))
    if generated.get("generation_mode") != "direct_complete_scene" or generated.get("matting") is not False:
        raise ValueError("scene.generated_manifest_invalid")
    default_job = json.loads(default_job_path.read_text(encoding="utf-8"))
    default_video = Path(str(default_job.get("video_path", ""))).resolve()
    default_avatar_id = str(default_job.get("speaking_avatar_id", ""))
    default_avatar = avatar_root / default_avatar_id
    default_avatar_manifest = json.loads((default_avatar / "manifest.json").read_text(encoding="utf-8"))
    source_sha = str(default_avatar_manifest.get("source_sha256", ""))
    source = next((item for item in manifest.payload["sources"] if item["sha256"] == source_sha), None)
    if source is None:
        raise ValueError("scene.source_identity_missing")
    source_path = (assets_root.resolve() / source["relative_path"]).resolve()
    if assets_root.resolve() not in source_path.parents or not source_path.is_file():
        raise FileNotFoundError("scene.source_asset_missing")

    bindings: list[dict] = []
    renditions: list[dict] = []
    for definition in DEFAULT_SCENES:
        scene_id = ScenePresetService.scene_id(definition.slug)
        if definition.slug == "blue-hour-living":
            video_source = default_video
            avatar_id = default_avatar_id
        else:
            record = generated.get("records", {}).get(definition.slug)
            if definition.slug not in GENERATED_SCENES or not isinstance(record, dict):
                raise ValueError(f"scene.generated_record_missing:{definition.slug}")
            video_source = Path(str(record.get("output", ""))).resolve()
            if not video_source.is_file() or _sha256(video_source) != record.get("output_sha256"):
                raise ValueError(f"scene.generated_output_mismatch:{definition.slug}")
            video_sha = _sha256(video_source)
            avatar_id = (
                f"wav2lip256_idle_p_{source_sha[:16]}_{video_sha[:8]}_"
                f"{SCENE_AVATAR_BUILD_REVISION}"
            )
        if not video_source.is_file():
            raise FileNotFoundError(f"scene.idle_missing:{definition.slug}")
        video_sha = _sha256(video_source)
        idle_target = binding_root / "assets" / f"{scene_id}-idle.mp4"
        if not idle_target.is_file() or _sha256(idle_target) != video_sha:
            _atomic_copy(video_source, idle_target)

        avatar_target = avatar_root / avatar_id
        if not avatar_target.is_dir():
            build(source_path, idle_target, avatar_root, avatar_id, preserve_frame=True)
        avatar_payload = _approve_avatar_manifest(
            avatar_target, source_sha=source_sha, idle_sha=video_sha
        )
        talking_sha = _sha256(avatar_target / "manifest.json")
        idle_rendition_id = str(uuid5(RENDITION_NAMESPACE, f"{scene_id}:idle:{video_sha}"))
        talking_rendition_id = str(uuid5(RENDITION_NAMESPACE, f"{scene_id}:talking:{talking_sha}"))
        bindings.append({
            "scene_id": scene_id,
            "slug": definition.slug,
            "idle_relative_path": f"assets/{scene_id}-idle.mp4",
            "idle_sha256": video_sha,
            "speaking_avatar_id": avatar_id,
            "talking_sha256": talking_sha,
            "idle_rendition_id": idle_rendition_id,
            "talking_rendition_id": talking_rendition_id,
        })
        for rendition_id, kind, sha256 in (
            (idle_rendition_id, "idle", video_sha),
            (talking_rendition_id, "talking", talking_sha),
        ):
            renditions.append({
                "rendition_id": rendition_id,
                "kind": kind,
                "source_ids": [source["source_id"]],
                "scene_id": scene_id,
                "status": "approved",
                "sha256": sha256,
            })

    binding_root.mkdir(parents=True, exist_ok=True)
    binding_manifest = {
        "schema_version": 1,
        "source_pack_id": manifest.payload["pack_id"],
        "source_sha256": source_sha,
        "bindings": sorted(bindings, key=lambda item: item["scene_id"]),
    }
    target = binding_root / "scene-bindings.v1.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(binding_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, target)
    committed = source_pack.register_renditions(renditions)
    return {
        "schema_version": 1,
        "result": "PASS",
        "revision": committed.revision,
        "active_scene_id": committed.payload.get("active_scene_id"),
        "binding_manifest": str(target),
        "bindings": bindings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--assets-root", type=Path, required=True)
    parser.add_argument("--backgrounds-root", type=Path, required=True)
    parser.add_argument("--generated-manifest", type=Path, required=True)
    parser.add_argument("--default-job", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(install(
        data_root=args.data_root,
        assets_root=args.assets_root,
        backgrounds_root=args.backgrounds_root,
        generated_manifest_path=args.generated_manifest,
        default_job_path=args.default_job,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
