from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.scene_preset_service import DEFAULT_SCENES, ScenePresetService
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository


REPO_ROOT = Path(__file__).resolve().parents[3]


def build(tmp_path: Path, *, enabled: bool = True, with_bindings: bool = False):
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir(parents=True)
    for index, definition in enumerate(DEFAULT_SCENES):
        (backgrounds / definition.filename).write_bytes(f"webp-scene-{index}".encode())
    manifests = JsonManifestRepository(tmp_path / "private")
    source_pack = SourcePackService(manifests)
    source_pack.add_source(
        sha256="a" * 64,
        relative_path="portrait/source.png",
        angle="front",
        appearance_label="已确认外观",
        consent_id="consent-1",
    )
    binding_root = tmp_path / "private" / "v2x" / "scene-renditions"
    avatar_root = tmp_path / "avatars"
    if with_bindings:
        manifest = source_pack.register_scenes([{
            "scene_id": ScenePresetService.scene_id(definition.slug),
            "label": definition.label,
            "asset_sha256": hashlib.sha256((backgrounds / definition.filename).read_bytes()).hexdigest(),
        } for definition in DEFAULT_SCENES])
        source_id = manifest.payload["sources"][0]["source_id"]
        bindings, renditions = [], []
        for definition in DEFAULT_SCENES:
            scene_id = ScenePresetService.scene_id(definition.slug)
            idle = binding_root / "assets" / f"{scene_id}-idle.mp4"
            idle.parent.mkdir(parents=True, exist_ok=True)
            idle.write_bytes(f"approved-idle-{definition.slug}".encode())
            idle_sha = hashlib.sha256(idle.read_bytes()).hexdigest()
            avatar_id = f"avatar_{definition.slug.replace('-', '_')}"
            avatar_dir = avatar_root / avatar_id
            avatar_dir.mkdir(parents=True)
            avatar_manifest = avatar_dir / "manifest.json"
            avatar_manifest.write_text(json.dumps({
                "avatar_id": avatar_id, "source_sha256": "a" * 64,
                "presentation": "complete_scene", "visual_approved": True,
                "frame_count": 160, "frame_size": [768, 432],
                "coordinates": [80, 320, 100, 300],
            }), encoding="utf-8")
            talking_sha = hashlib.sha256(avatar_manifest.read_bytes()).hexdigest()
            idle_id, talking_id = str(uuid4()), str(uuid4())
            bindings.append({
                "scene_id": scene_id, "slug": definition.slug,
                "engine": "wav2lip",
                "idle_relative_path": f"assets/{scene_id}-idle.mp4",
                "idle_sha256": idle_sha, "speaking_avatar_id": avatar_id,
                "talking_sha256": talking_sha,
                "idle_rendition_id": idle_id, "talking_rendition_id": talking_id,
            })
            renditions.extend([
                {"rendition_id": idle_id, "kind": "idle", "source_ids": [source_id], "scene_id": scene_id, "status": "approved", "sha256": idle_sha},
                {"rendition_id": talking_id, "kind": "talking", "source_ids": [source_id], "scene_id": scene_id, "status": "approved", "sha256": talking_sha},
            ])
        binding_root.mkdir(parents=True, exist_ok=True)
        (binding_root / "scene-bindings.v1.json").write_text(json.dumps({
            "schema_version": 1, "bindings": bindings,
        }), encoding="utf-8")
        source_pack.register_renditions(renditions)
    scenes = ScenePresetService(
        source_pack, backgrounds, binding_root=binding_root, avatar_root=avatar_root,
    )
    registry = ModelRegistry(REPO_ROOT)
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        source_pack_service=source_pack,
        scene_preset_service=scenes,
        experience_flags={"source_pack": True, "scene_presets": enabled},
    ).build_app()
    return TestClient(app), manifests, backgrounds, scenes


def test_catalog_uses_real_hashes_stable_ids_and_idempotent_revision(tmp_path):
    client, manifests, backgrounds, _ = build(tmp_path)
    first = client.get("/api/v1/scene-presets")
    assert first.status_code == 200, first.text
    body = first.json()
    assert len(body["items"]) == 4
    assert body["revision"] == 2
    assert body["active_scene_id"] is None
    assert all(item["quality_status"] == "preview_only" for item in body["items"])
    assert all(item["can_activate"] is False for item in body["items"])
    assert all(item["preview_url"].startswith("/backgrounds/") for item in body["items"])
    expected = {
        definition.slug: hashlib.sha256((backgrounds / definition.filename).read_bytes()).hexdigest()
        for definition in DEFAULT_SCENES
    }
    assert {item["slug"]: item["asset_sha256"] for item in body["items"]} == expected
    active = manifests.active_bytes()

    second = client.get("/api/v1/scene-presets")
    assert second.status_code == 200
    assert second.json() == body
    assert manifests.active_bytes() == active
    assert str(tmp_path) not in first.text


def test_changed_asset_advances_revision_and_missing_asset_preserves_manifest(tmp_path):
    client, manifests, backgrounds, _ = build(tmp_path)
    initial = client.get("/api/v1/scene-presets").json()
    target = backgrounds / DEFAULT_SCENES[0].filename
    target.write_bytes(b"changed-real-webp")
    changed = client.get("/api/v1/scene-presets")
    assert changed.status_code == 200
    assert changed.json()["revision"] == initial["revision"] + 1
    assert changed.json()["items"][0]["asset_sha256"] != initial["items"][0]["asset_sha256"]
    stable = manifests.active_bytes()

    (backgrounds / DEFAULT_SCENES[1].filename).unlink()
    failed = client.get("/api/v1/scene-presets")
    assert failed.status_code == 503
    assert manifests.active_bytes() == stable


def test_feature_flag_disables_scene_catalog(tmp_path):
    client, _, _, _ = build(tmp_path, enabled=False)
    assert client.get("/api/v1/scene-presets").status_code == 404


def test_approved_bindings_activate_with_cas_and_survive_catalog_reload(tmp_path):
    client, manifests, _, scenes = build(tmp_path, with_bindings=True)
    catalog = client.get("/api/v1/scene-presets").json()
    assert all(item["can_activate"] for item in catalog["items"])
    assert all(item["quality_status"] == "approved" for item in catalog["items"])
    target = catalog["items"][1]

    stale = client.post(
        f"/api/v1/scene-presets/{target['scene_id']}/activate",
        json={"expected_revision": catalog["revision"] - 1},
    )
    assert stale.status_code == 409
    assert manifests.load().payload["active_scene_id"] is None

    activated = client.post(
        f"/api/v1/scene-presets/{target['scene_id']}/activate",
        json={"expected_revision": catalog["revision"]},
    )
    assert activated.status_code == 200, activated.text
    body = activated.json()
    assert body["revision"] == catalog["revision"] + 1
    assert body["active_scene_id"] == target["scene_id"]
    assert next(item for item in body["items"] if item["scene_id"] == target["scene_id"])["quality_status"] == "active"
    assert client.get(target["idle_url"]).headers["cache-control"] == "no-store, private"
    active = scenes.active_avatar()
    assert active is not None
    assert active["scene_id"] == target["scene_id"]
    assert active["engine"] == "wav2lip"
    assert active["single_surface_ready"] is True


def test_musetalk_binding_reports_runtime_engine(tmp_path):
    client, manifests, _, scenes = build(tmp_path, with_bindings=True)
    binding_path = tmp_path / "private" / "v2x" / "scene-renditions" / "scene-bindings.v1.json"
    payload = json.loads(binding_path.read_text(encoding="utf-8"))
    target = payload["bindings"][0]
    target["engine"] = "musetalk"
    avatar_manifest_path = tmp_path / "avatars" / target["speaking_avatar_id"] / "manifest.json"
    avatar_manifest = json.loads(avatar_manifest_path.read_text(encoding="utf-8"))
    avatar_manifest["engine"] = "musetalk15"
    avatar_manifest_path.write_text(json.dumps(avatar_manifest), encoding="utf-8")
    target["talking_sha256"] = hashlib.sha256(avatar_manifest_path.read_bytes()).hexdigest()
    binding_path.write_text(json.dumps(payload), encoding="utf-8")
    renditions = manifests.load().to_dict()["renditions"]
    for item in renditions:
        if item["scene_id"] == target["scene_id"] and item["kind"] == "talking":
            item["sha256"] = target["talking_sha256"]
    source_pack = SourcePackService(manifests)
    source_pack.register_renditions(renditions)
    current = manifests.load()
    source_pack.activate_scene(target["scene_id"], expected_revision=current.revision)
    active = scenes.active_avatar()
    assert active is not None
    assert active["engine"] == "musetalk"
