from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.scene_preset_service import DEFAULT_SCENES, ScenePresetService
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository


REPO_ROOT = Path(__file__).resolve().parents[3]


def build(tmp_path: Path, *, enabled: bool = True):
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
    scenes = ScenePresetService(source_pack, backgrounds)
    registry = ModelRegistry(REPO_ROOT)
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        source_pack_service=source_pack,
        scene_preset_service=scenes,
        experience_flags={"source_pack": True, "scene_presets": enabled},
    ).build_app()
    return TestClient(app), manifests, backgrounds


def test_catalog_uses_real_hashes_stable_ids_and_idempotent_revision(tmp_path):
    client, manifests, backgrounds = build(tmp_path)
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
    client, manifests, backgrounds = build(tmp_path)
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
    client, _, _ = build(tmp_path, enabled=False)
    assert client.get("/api/v1/scene-presets").status_code == 404

