from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository
from ops.select_avatar_engine import select


def _prepare(root: Path, engine: str = "musetalk") -> tuple[str, str]:
    scene_ids = [str(uuid4()) for _ in range(4)]
    repository = JsonManifestRepository(root)
    service = SourcePackService(repository)
    _, source, _ = service.add_source(
        sha256="a" * 64,
        relative_path="portrait/source.png",
        angle="front",
        appearance_label="approved",
        consent_id="consent-1",
    )
    service.register_scenes([{
        "scene_id": scene_id,
        "label": scene_id,
        "asset_sha256": str(index) * 64,
    } for index, scene_id in enumerate(scene_ids, start=1)])
    bindings = []
    renditions = []
    for index, scene_id in enumerate(scene_ids):
        idle_id = str(uuid4())
        talking_id = str(uuid4())
        avatar_id = f"{engine}-avatar-{index}"
        dataset = root / "avatar" / "avatars" / avatar_id
        dataset.mkdir(parents=True)
        (dataset / "manifest.json").write_text(json.dumps({
            "avatar_id": avatar_id,
            "engine": "musetalk15" if engine == "musetalk" else "wav2lip",
            "visual_approved": True,
        }), encoding="utf-8")
        bindings.append({
            "scene_id": scene_id,
            "engine": engine,
            "speaking_avatar_id": avatar_id,
            "idle_rendition_id": idle_id,
            "talking_rendition_id": talking_id,
            "idle_sha256": "b" * 64,
            "talking_sha256": "c" * 64,
        })
        renditions.extend([
            {"rendition_id": idle_id, "kind": "idle", "source_ids": [source["source_id"]], "scene_id": scene_id, "status": "approved", "sha256": "b" * 64},
            {"rendition_id": talking_id, "kind": "talking", "source_ids": [source["source_id"]], "scene_id": scene_id, "status": "approved", "sha256": "c" * 64},
        ])
    binding_root = root / "v2x" / "scene-renditions"
    binding_root.mkdir(parents=True)
    (binding_root / f"scene-bindings.{engine}.v1.json").write_text(json.dumps({
        "schema_version": 1,
        "source_sha256": "a" * 64,
        "bindings": bindings,
    }), encoding="utf-8")
    service.register_renditions(renditions)
    current = service.load()
    assert current is not None
    service.activate_scene(scene_ids[2], expected_revision=current.revision)
    return scene_ids[2], bindings[2]["speaking_avatar_id"]


def test_select_avatar_engine_updates_binding_and_bootstrap_atomically(tmp_path):
    scene_id, avatar_id = _prepare(tmp_path)
    result = select(tmp_path, "musetalk")
    assert result["active_scene_id"] == scene_id
    assert result["avatar_id"] == avatar_id
    assert (tmp_path / "bootstrap" / "avatar-engine").read_text().strip() == "musetalk"
    assert (tmp_path / "bootstrap" / "avatar-id").read_text().strip() == avatar_id
    active = json.loads(
        (tmp_path / "v2x" / "scene-renditions" / "scene-bindings.v1.json").read_text()
    )
    assert {item["engine"] for item in active["bindings"]} == {"musetalk"}


def test_select_avatar_engine_rejects_partial_or_unapproved_variant(tmp_path):
    _prepare(tmp_path)
    target = tmp_path / "v2x" / "scene-renditions" / "scene-bindings.musetalk.v1.json"
    payload = json.loads(target.read_text())
    payload["bindings"].pop()
    target.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="binding_variant_invalid"):
        select(tmp_path, "musetalk")
