from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[3]
PNG = b"\x89PNG\r\n\x1a\n" + b"acceptance-image"
WAV = b"RIFF" + b"\x00" * 32


def stack(tmp_path, **gateway_kwargs):
    db = tmp_path / "complete.db"
    repo = SqliteRepository(db, ROOT / "migrations" / "0001_init.sql")
    registry = ModelRegistry(ROOT)
    app = ApiGateway(
        registry, HealthAggregator(registry), repository=repo, assets_root=tmp_path / "assets",
        **gateway_kwargs,
    ).build_app()
    return TestClient(app), repo, db


def upload(client, kind, name, body):
    return client.post(
        f"/api/v1/assets/{kind}/preview",
        files={"file": (name, body, "application/octet-stream")},
    )


def test_consent_blocks_upload_activation_and_revocation_withdraws_pointer(tmp_path):
    client, repo, _ = stack(tmp_path)
    assert upload(client, "portrait", "first.png", PNG).status_code == 403
    granted = client.post("/api/v1/consents", json={"scope": "portrait", "policy_version": "v1"})
    assert granted.status_code == 200 and granted.json()["granted"] == 1
    first = upload(client, "portrait", "first.png", PNG).json()
    second = upload(client, "portrait", "second.png", PNG + b"2").json()
    assert first["status"] == second["status"] == "previewed"
    assert client.post(f"/api/v1/assets/{first['id']}/activate").status_code == 200
    assert repo.get_active_asset("portrait")["id"] == first["id"]
    content = client.get("/api/v1/assets/portrait/active/content")
    assert content.status_code == 200 and content.content == PNG
    assert content.headers["cache-control"] == "no-store, private"
    assert client.post(f"/api/v1/assets/{second['id']}/activate").status_code == 200
    assert repo.get_active_asset("portrait")["id"] == second["id"]
    restored = client.post("/api/v1/assets/portrait/restore")
    assert restored.status_code == 200 and restored.json()["id"] == first["id"]
    revoked = client.delete("/api/v1/consents/portrait")
    assert revoked.status_code == 200 and revoked.json()["granted"] is False
    assert repo.conn.execute("SELECT COUNT(*) FROM active_assets WHERE kind='portrait'").fetchone()[0] == 0
    assert repo.get_active_asset("portrait") is None
    assert client.post(f"/api/v1/assets/{second['id']}/activate").status_code == 403
    assert upload(client, "portrait", "third.png", PNG).status_code == 403
    audits = client.get("/api/v1/audit", params={"entity": "consent"}).json()["items"]
    assert {item["action"] for item in audits} >= {"consent.granted", "consent.revoked"}


def test_voice_revocation_clears_process_private_cache(tmp_path):
    cleared = []
    client, _repo, _ = stack(tmp_path, privacy_cache_clear=lambda: cleared.append(True))
    client.post("/api/v1/consents", json={"scope": "voice", "policy_version": "v1"})
    assert client.delete("/api/v1/consents/voice").status_code == 200
    assert cleared == [True]


@pytest.mark.parametrize("fault_point", ["after_archive", "after_pointer", "before_commit"])
def test_asset_activation_failure_preserves_previous_pointer(tmp_path, fault_point):
    client, repo, _ = stack(tmp_path)
    client.post("/api/v1/consents", json={"scope": "voice"})
    one = upload(client, "voice", "one.wav", WAV).json()
    two = upload(client, "voice", "two.wav", WAV + b"2").json()
    repo.activate_asset(one["id"])

    def fault(point):
        if point == fault_point:
            raise RuntimeError(point)

    with pytest.raises(RuntimeError):
        repo.activate_asset(two["id"], fault_injector=fault)
    active = repo.conn.execute("SELECT asset_id FROM active_assets WHERE kind='voice'").fetchone()
    assert active["asset_id"] == one["id"]
    assert repo.get_asset_version(one["id"])["status"] == "active"
    assert repo.get_asset_version(two["id"])["status"] == "previewed"


def test_complete_profile_optimistic_concurrency_history_and_restart(tmp_path):
    client, repo, db = stack(tmp_path)
    payload = {
        "name": "小雅", "user_nickname": "阿林", "persona": "温柔自然",
        "relationship_context": "长期伴侣", "example_dialogue": "你：累了。她：我陪你。",
        "expected_version": 0,
    }
    first = client.put("/api/v1/profile", json=payload)
    assert first.status_code == 200 and first.json()["version"] == 1
    update = {**payload, "persona": "温柔、自然、会倾听", "expected_version": 1}
    second = client.put("/api/v1/profile", json=update)
    assert second.status_code == 200 and second.json()["version"] == 2
    stale = client.put("/api/v1/profile", json={**payload, "expected_version": 1})
    assert stale.status_code == 409
    assert repo.conn.execute("SELECT COUNT(*) FROM profile_history").fetchone()[0] == 1
    repo.close()
    reopened = SqliteRepository(db, ROOT / "migrations" / "0001_init.sql")
    profile = reopened.get_profile()
    assert profile is not None and profile.persona == "温柔、自然、会倾听" and profile.version == 2
    reopened.close()
