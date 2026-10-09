#!/usr/bin/env python3
"""Atomically select one prepared Avatar engine without dual residency."""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def _atomic_text(target: Path, value: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(value + "\n", encoding="utf-8")
    os.replace(temporary, target)


def select(data_root: Path, engine: str) -> dict:
    if engine not in {"wav2lip", "musetalk"}:
        raise ValueError("avatar.engine_invalid")
    data_root = data_root.resolve()
    binding_root = data_root / "v2x" / "scene-renditions"
    source = binding_root / f"scene-bindings.{engine}.v1.json"
    target = binding_root / "scene-bindings.v1.json"
    if not source.is_file():
        raise FileNotFoundError(f"avatar.binding_variant_missing:{engine}")
    payload = json.loads(source.read_text(encoding="utf-8"))
    bindings = payload.get("bindings")
    if payload.get("schema_version") != 1 or not isinstance(bindings, list) or len(bindings) != 4:
        raise ValueError("avatar.binding_variant_invalid")
    avatar_root = data_root / "avatar" / "avatars"
    for item in bindings:
        declared = str(item.get("engine", "wav2lip"))
        if declared != engine:
            raise ValueError("avatar.binding_engine_mismatch")
        avatar_id = str(item.get("speaking_avatar_id", ""))
        manifest_path = avatar_root / avatar_id / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"avatar.dataset_missing:{avatar_id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        actual = str(manifest.get("engine", "wav2lip"))
        if actual == "musetalk15":
            actual = "musetalk"
        if actual != engine or manifest.get("visual_approved") is not True:
            raise ValueError(f"avatar.dataset_not_approved:{avatar_id}")

    repository = JsonManifestRepository(data_root)
    service = SourcePackService(repository)
    source_pack = service.load()
    if source_pack is None:
        raise ValueError("source_pack.required")
    active_scene_id = str(source_pack.payload.get("active_scene_id", ""))
    active = next((item for item in bindings if item.get("scene_id") == active_scene_id), None)
    if active is None:
        raise ValueError("avatar.active_scene_binding_missing")

    source_sha = str(payload.get("source_sha256", ""))
    source_record = next(
        (item for item in source_pack.payload["sources"] if item["sha256"] == source_sha),
        None,
    )
    if source_record is None:
        raise ValueError("avatar.source_identity_missing")
    renditions: list[dict] = []
    for item in bindings:
        for rendition_id, kind, sha256 in (
            (item["idle_rendition_id"], "idle", item["idle_sha256"]),
            (item["talking_rendition_id"], "talking", item["talking_sha256"]),
        ):
            renditions.append({
                "rendition_id": rendition_id,
                "kind": kind,
                "source_ids": [source_record["source_id"]],
                "scene_id": item["scene_id"],
                "status": "active" if item["scene_id"] == active_scene_id else "approved",
                "sha256": sha256,
            })
    committed = service.register_renditions(renditions)

    _atomic_copy(source, target)
    _atomic_text(data_root / "bootstrap" / "avatar-engine", engine)
    _atomic_text(data_root / "bootstrap" / "avatar-id", str(active["speaking_avatar_id"]))
    return {
        "result": "PASS",
        "engine": engine,
        "active_scene_id": active_scene_id,
        "avatar_id": active["speaking_avatar_id"],
        "revision": committed.revision,
        "binding_manifest": str(target),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--engine", choices=("wav2lip", "musetalk"), required=True)
    args = parser.parse_args()
    print(json.dumps(select(args.data_root, args.engine), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
