from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from cyberwife.application.scene_preset_service import DEFAULT_SCENES, ScenePresetService
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository
from ops.install_appearance_combinations import install


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(tmp_path: Path) -> tuple[Path, Path]:
    data_root = tmp_path / "data"
    repo = JsonManifestRepository(data_root)
    service = SourcePackService(repo)
    source = service.add_source(
        sha256="a" * 64,
        relative_path="portrait/source.png",
        angle="front",
        appearance_label="已批准人物",
        consent_id="consent-1",
    )[0]
    service.register_scenes([{
        "scene_id": ScenePresetService.scene_id(item.slug),
        "label": item.label,
        "asset_sha256": f"{index + 1}" * 64,
    } for index, item in enumerate(DEFAULT_SCENES)])
    binding_root = data_root / "v2x" / "scene-renditions"
    avatar_root = data_root / "avatar" / "avatars"
    red_bindings = []
    for index, definition in enumerate(DEFAULT_SCENES):
        scene_id = ScenePresetService.scene_id(definition.slug)
        idle = binding_root / "assets" / f"{scene_id}-idle.mp4"
        idle.parent.mkdir(parents=True, exist_ok=True)
        idle.write_bytes(f"red-idle-{index}".encode())
        avatar_id = f"musetalk15_red_{index}"
        avatar_manifest = avatar_root / avatar_id / "manifest.json"
        avatar_manifest.parent.mkdir(parents=True)
        avatar_manifest.write_text(json.dumps({
            "avatar_id": avatar_id, "source_sha256": "a" * 64,
            "presentation": "complete_scene", "visual_approved": True,
            "engine": "musetalk15", "frame_count": 250,
        }), encoding="utf-8")
        red_bindings.append({
            "scene_id": scene_id, "slug": definition.slug, "engine": "musetalk",
            "idle_relative_path": idle.relative_to(binding_root).as_posix(),
            "idle_sha256": sha(idle), "speaking_avatar_id": avatar_id,
            "talking_sha256": sha(avatar_manifest),
            "idle_rendition_id": str(uuid4()), "talking_rendition_id": str(uuid4()),
        })
    binding_root.mkdir(parents=True, exist_ok=True)
    (binding_root / "scene-bindings.v1.json").write_text(json.dumps({
        "schema_version": 1, "source_pack_id": source.payload["pack_id"],
        "source_sha256": "a" * 64, "bindings": red_bindings,
    }), encoding="utf-8")

    appearance_id = str(uuid4())
    records = {}
    for index, definition in enumerate(DEFAULT_SCENES[1:]):
        scene_id = ScenePresetService.scene_id(definition.slug)
        idle = tmp_path / "candidate" / f"{definition.slug}.mp4"
        idle.parent.mkdir(parents=True, exist_ok=True)
        idle.write_bytes(f"blue-idle-{index}".encode())
        avatar_id = f"musetalk15_blue_{index}"
        avatar_manifest = avatar_root / avatar_id / "manifest.json"
        avatar_manifest.parent.mkdir(parents=True)
        avatar_manifest.write_text(json.dumps({
            "avatar_id": avatar_id, "source_sha256": "a" * 64,
            "presentation": "complete_scene", "visual_approved": False,
            "engine": "musetalk15", "frame_count": 250,
        }), encoding="utf-8")
        records[definition.slug] = {
            "scene_id": scene_id, "appearance_id": appearance_id,
            "status": "staged", "idle": str(idle), "idle_sha256": sha(idle),
            "musetalk_avatar_id": avatar_id,
            "musetalk_manifest_sha256": sha(avatar_manifest),
        }
    candidate = tmp_path / "candidate" / "candidate-manifest.json"
    candidate.write_text(json.dumps({
        "schema_version": 1, "appearance_id": appearance_id,
        "appearance_label": "蓝白碎花上衣", "engine": "musetalk",
        "presentation": "complete_scene", "matting": False,
        "visual_approval_required": True, "records": records,
    }), encoding="utf-8")
    return data_root, candidate


def test_installs_two_appearances_and_seven_reversible_combinations(tmp_path):
    data_root, candidate = prepare(tmp_path)
    result = install(data_root=data_root, candidate_manifest_path=candidate)
    assert result["result"] == "PASS"
    assert result["appearance_count"] == 2
    assert result["combination_count"] == 7
    manifest = JsonManifestRepository(data_root).load()
    assert manifest is not None
    assert len(manifest.payload["appearances"]) == 2
    assert sum(item["status"] == "active" for item in manifest.payload["renditions"]) == 0
    bindings = json.loads((data_root / "v2x/scene-renditions/scene-bindings.v2.json").read_text())
    assert bindings["schema_version"] == 2
    assert len({(item["appearance_id"], item["scene_id"]) for item in bindings["bindings"]}) == 7
    for item in json.loads(candidate.read_text())["records"].values():
        avatar = json.loads((data_root / "avatar/avatars" / item["musetalk_avatar_id"] / "manifest.json").read_text())
        assert avatar["visual_approved"] is True
    repeated = install(data_root=data_root, candidate_manifest_path=candidate)
    assert repeated["revision"] == result["revision"]


def test_hash_mismatch_fails_without_publishing_v2_binding(tmp_path):
    data_root, candidate = prepare(tmp_path)
    payload = json.loads(candidate.read_text())
    next(iter(payload["records"].values()))["idle_sha256"] = "0" * 64
    candidate.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="candidate_hash_mismatch"):
        install(data_root=data_root, candidate_manifest_path=candidate)
    assert not (data_root / "v2x/scene-renditions/scene-bindings.v2.json").exists()
