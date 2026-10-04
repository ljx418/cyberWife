from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.avatar_asset_service import AvatarAssetService
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[3]
PNG = b"\x89PNG\r\n\x1a\n" + b"real-api-route-test"


def test_portrait_api_builds_then_atomically_activates_matching_avatar(tmp_path, monkeypatch):
    repo = SqliteRepository(tmp_path / "api.db", ROOT / "migrations" / "0001_init.sql")
    registry = ModelRegistry(ROOT)
    service = AvatarAssetService(
        repo,
        assets_root=tmp_path / "assets",
        avatar_root=tmp_path / "avatars",
    )

    def fake_build(source: Path, output_root: Path, avatar_id: str) -> Path:
        target = output_root / avatar_id
        target.mkdir(parents=True)
        (target / "manifest.json").write_text(json.dumps({
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "frame_count": 1,
            "frame_size": [512, 768],
            "coordinates": [100, 400, 80, 320],
        }), encoding="utf-8")
        return target

    monkeypatch.setattr("ops.build_static_avatar.build", fake_build)
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        repository=repo,
        assets_root=tmp_path / "assets",
        avatar_asset_service=service,
    ).build_app()
    client = TestClient(app)
    client.post("/api/v1/consents", json={"scope": "portrait", "policy_version": "v1"})
    uploaded = client.post(
        "/api/v1/assets/portrait/preview",
        files={"file": ("portrait.png", PNG, "image/png")},
    ).json()

    assert client.post(f"/api/v1/assets/{uploaded['id']}/activate").status_code == 409
    queued = client.post(f"/api/v1/assets/{uploaded['id']}/avatar-builds")
    assert queued.status_code == 202
    build = client.get(f"/api/v1/avatar-builds/{queued.json()['id']}").json()
    assert build["status"] == "ready"
    activated = client.post(f"/api/v1/avatar-builds/{build['id']}/activate")
    assert activated.status_code == 200
    active = client.get("/api/v1/avatar/active").json()
    assert active["avatar_id"] == build["avatar_id"]
    assert active["source_sha256"] == hashlib.sha256(PNG).hexdigest()
