from __future__ import annotations

import hashlib
import io
import struct
import zlib
from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.asset_store import AssetStore
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository
from cyberwife.ports.assets import ManifestRevisionConflict


REPO_ROOT = Path(__file__).resolve().parents[3]


def png(rgb: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"\x00" + bytes(rgb)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def build(tmp_path: Path, *, enabled: bool = True):
    db = tmp_path / "source-pack.db"
    repository = SqliteRepository(db, schema_sql_path=REPO_ROOT / "migrations" / "0001_init.sql")
    if not repository.consent_active("portrait"):
        repository.grant_consent("portrait", "test-v2x")
    asset_store = AssetStore(tmp_path / "assets")
    manifests = JsonManifestRepository(tmp_path / "private")
    source_pack = SourcePackService(manifests)
    registry = ModelRegistry(REPO_ROOT)
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        repository=repository,
        asset_store=asset_store,
        source_pack_service=source_pack,
        experience_flags={"source_pack": enabled},
    ).build_app()
    return TestClient(app), repository, asset_store, manifests


def upload(client: TestClient, payload: bytes, angle: str, label: str):
    return client.post(
        "/api/v1/source-pack/sources",
        files={"file": (f"{angle}.png", io.BytesIO(payload), "image/png")},
        data={"angle": angle, "appearance_label": label},
    )


def test_import_four_sources_persists_ids_and_serves_private_content(tmp_path):
    client, repository, _, _ = build(tmp_path)
    inputs = [
        (png((255, 0, 0)), "front", "红色针织上衣"),
        (png((0, 255, 0)), "left", "红色针织上衣"),
        (png((0, 0, 255)), "full_body", "蓝白碎花连衣裙"),
        (png((240, 210, 80)), "right", "米色家居服"),
    ]
    for index, (payload, angle, label) in enumerate(inputs, start=1):
        response = upload(client, payload, angle, label)
        assert response.status_code == 200, response.text
        assert response.json()["revision"] == index
        assert response.json()["created"] is True
    listing = client.get("/api/v1/source-pack")
    assert listing.status_code == 200
    body = listing.json()
    assert body["revision"] == 4
    assert [item["angle"] for item in body["sources"]] == ["front", "left", "full_body", "right"]
    assert all(item["provenance"] == "local_upload" for item in body["sources"])
    assert all(item["consent_id"].startswith("consent-") for item in body["sources"])
    assert "relative_path" not in listing.text and str(tmp_path) not in listing.text
    first = body["sources"][0]
    content = client.get(first["content_url"])
    assert content.status_code == 200
    assert content.content == inputs[0][0]
    assert content.headers["cache-control"] == "no-store, private"
    pack_id = body["pack_id"]
    source_ids = [item["source_id"] for item in body["sources"]]
    repository.close()

    restarted, repository2, _, _ = build(tmp_path)
    after = restarted.get("/api/v1/source-pack").json()
    assert after["pack_id"] == pack_id
    assert after["revision"] == 4
    assert [item["source_id"] for item in after["sources"]] == source_ids
    repository2.close()


def test_duplicate_is_idempotent_and_invalid_metadata_preserves_manifest(tmp_path):
    client, repository, asset_store, manifests = build(tmp_path)
    payload = png((1, 2, 3))
    first = upload(client, payload, "front", "深色上衣")
    assert first.status_code == 200
    source_id = first.json()["source"]["source_id"]
    active_bytes = manifests.active_bytes()
    files_before = sorted(path.name for path in (asset_store.root / "portrait").iterdir())

    duplicate = upload(client, payload, "front", "不会静默改写的标签")
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["revision"] == 1
    assert duplicate.json()["source"]["source_id"] == source_id
    assert manifests.active_bytes() == active_bytes
    assert sorted(path.name for path in (asset_store.root / "portrait").iterdir()) == files_before

    invalid = upload(client, png((4, 5, 6)), "diagonal", "测试")
    assert invalid.status_code == 422
    assert manifests.active_bytes() == active_bytes
    assert sorted(path.name for path in (asset_store.root / "portrait").iterdir()) == files_before
    repository.close()


def test_commit_conflict_cleans_new_file_and_flag_disables_api(tmp_path, monkeypatch):
    client, repository, asset_store, manifests = build(tmp_path)
    first = upload(client, png((8, 8, 8)), "front", "基础外观")
    assert first.status_code == 200
    active_hash = hashlib.sha256(manifests.active_bytes() or b"").hexdigest()
    files_before = sorted(path.name for path in (asset_store.root / "portrait").iterdir())

    monkeypatch.setattr(manifests, "commit", lambda **_: (_ for _ in ()).throw(ManifestRevisionConflict("injected")))
    failed = upload(client, png((9, 9, 9)), "left", "另一角度")
    assert failed.status_code == 409
    assert hashlib.sha256(manifests.active_bytes() or b"").hexdigest() == active_hash
    assert sorted(path.name for path in (asset_store.root / "portrait").iterdir()) == files_before
    repository.close()

    disabled, repository2, _, _ = build(tmp_path / "disabled", enabled=False)
    assert disabled.get("/api/v1/source-pack").status_code == 404
    assert upload(disabled, png((1, 1, 1)), "front", "测试").status_code == 404
    repository2.close()


def test_rejects_non_image_and_oversize_without_creating_manifest(tmp_path):
    client, repository, asset_store, manifests = build(tmp_path)
    audio_named_png = b"RIFF" + b"\x00" * 32
    response = upload(client, audio_named_png, "front", "伪装文件")
    assert response.status_code == 422
    assert manifests.load() is None
    portrait = asset_store.root / "portrait"
    assert not portrait.exists() or list(portrait.iterdir()) == []

    too_large = b"\x89PNG\r\n\x1a\n" + b"0" * (20 * 1024 * 1024)
    response = upload(client, too_large, "front", "超限")
    assert response.status_code == 413
    assert manifests.load() is None
    repository.close()


def test_existing_v1_active_portrait_is_bootstrapped_without_switching_it(tmp_path):
    client, repository, asset_store, manifests = build(tmp_path)
    original = tmp_path / "v1-active.png"
    original.write_bytes(png((22, 33, 44)))
    metadata = asset_store.ingest("portrait", "v1-active.png", original)
    metadata["filename_or_revision"] = "v1-active.png"
    asset = repository.create_asset_version(metadata)
    before = repository.activate_asset(int(asset["id"]))

    response = client.get("/api/v1/source-pack")
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert len(body["sources"]) == 1
    assert body["sources"][0]["provenance"] == "v1_active_asset"
    assert body["sources"][0]["sha256"] == metadata["sha256"]
    assert manifests.load().payload["legacy_asset_id"] == asset["id"]
    assert repository.get_active_asset("portrait")["id"] == before["id"]
    repository.close()
