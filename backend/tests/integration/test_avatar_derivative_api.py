from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.avatar_asset_service import AvatarAssetService
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.infrastructure.sqlite_repository import SqliteRepository
from cyberwife.infrastructure.asset_store import AssetStore


ROOT = Path(__file__).resolve().parents[3]
PNG = b"\x89PNG\r\n\x1a\n" + b"real-api-route-test"


def test_portrait_api_builds_then_atomically_activates_matching_avatar(tmp_path, monkeypatch):
    repo = SqliteRepository(tmp_path / "api.db", ROOT / "migrations" / "0001_init.sql")
    registry = ModelRegistry(ROOT)
    asset_store = AssetStore(tmp_path / "assets")
    service = AvatarAssetService(
        repo,
        asset_store=asset_store,
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
        asset_store=asset_store,
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


def test_idle_generation_requires_preview_then_promotes_approved_loop(tmp_path, monkeypatch):
    repo = SqliteRepository(tmp_path / "api.db", ROOT / "migrations" / "0001_init.sql")
    registry = ModelRegistry(ROOT)
    asset_store = AssetStore(tmp_path / "assets")

    pipeline_runs = 0

    def fake_idle_pipeline(source: Path, job_dir: Path, progress) -> dict:
        nonlocal pipeline_runs
        pipeline_runs += 1
        progress("frontalizing", 30)
        frontal = job_dir / "frontal.png"
        frontal.write_bytes(source.read_bytes())
        progress("building_seamless_loop", 80)
        video = job_dir / "idle-loop-10s.mp4"
        video.write_bytes(b"real-local-idle-loop")
        scenes = job_dir / "scenes"
        scenes.mkdir()
        outputs = {}
        for scene_id in (
            "blue-hour-living", "garden-sunroom",
            "morning-bedroom", "rainy-library",
        ):
            scene_video = scenes / f"idle-{scene_id}.mp4"
            scene_video.write_bytes(f"scene:{scene_id}".encode())
            outputs[scene_id] = {"path": str(scene_video)}
        scene_manifest = scenes / "scene-composite-manifest.json"
        scene_manifest.write_text(json.dumps({"outputs": outputs}), encoding="utf-8")
        return {
            "frontal_path": str(frontal),
            "video_path": str(video),
            "scene_manifest_path": str(scene_manifest),
        }

    service = AvatarAssetService(
        repo,
        asset_store=asset_store,
        avatar_root=tmp_path / "avatars",
        idle_job_root=tmp_path / "idle-jobs",
        idle_pipeline_runner=fake_idle_pipeline,
    )

    def fake_static_build(source: Path, output_root: Path, avatar_id: str) -> Path:
        target = output_root / avatar_id
        target.mkdir(parents=True)
        (target / "manifest.json").write_text(json.dumps({
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "frame_count": 1,
            "frame_size": [512, 768],
            "coordinates": [100, 400, 80, 320],
        }), encoding="utf-8")
        return target

    def fake_video_build(
        source: Path,
        video: Path,
        output_root: Path,
        avatar_id: str,
        *,
        preserve_frame: bool = False,
    ) -> Path:
        assert video.read_bytes() in {b"real-local-idle-loop", b"approved-idle"}
        target = output_root / avatar_id
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(json.dumps({
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "frame_count": 160,
            "frame_size": [768, 432] if preserve_frame else [512, 768],
            "coordinates": [100, 400, 80, 320],
            "presentation": "complete_scene" if preserve_frame else "portrait",
        }), encoding="utf-8")
        return target

    monkeypatch.setattr("ops.build_static_avatar.build", fake_static_build)
    monkeypatch.setattr("ops.build_video_avatar.build", fake_video_build)
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        repository=repo,
        assets_root=tmp_path / "assets",
        asset_store=asset_store,
        avatar_asset_service=service,
    ).build_app()
    client = TestClient(app)
    client.post("/api/v1/consents", json={"scope": "portrait", "policy_version": "v1"})
    uploaded = client.post(
        "/api/v1/assets/portrait/preview",
        files={"file": ("portrait.png", PNG, "image/png")},
    ).json()
    build = client.post(f"/api/v1/assets/{uploaded['id']}/avatar-builds").json()
    derivative_id = build["id"]

    assert client.post(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/approve"
    ).status_code == 409
    generated = client.post(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation"
    )
    assert generated.status_code == 202
    job = client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation"
    ).json()
    assert job["status"] == "awaiting_approval"
    assert job["progress"] == 100
    assert job["has_frontal_preview"] is True
    assert job["has_video_preview"] is True
    assert job["has_scene_previews"] is True
    assert job["scene_ids"] == [
        "blue-hour-living", "garden-sunroom",
        "morning-bedroom", "rainy-library",
    ]
    repeated = client.post(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation"
    )
    assert repeated.status_code == 202
    assert repeated.json()["status"] == "awaiting_approval"
    assert pipeline_runs == 1

    frontal = client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/frontal"
    )
    video = client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/video"
    )
    assert frontal.content == PNG
    assert frontal.headers["cache-control"] == "no-store, private"
    assert video.content == b"real-local-idle-loop"
    assert video.headers["content-type"].startswith("video/mp4")
    scene = client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/scenes/rainy-library"
    )
    assert scene.content == b"scene:rainy-library"
    assert scene.headers["cache-control"] == "no-store, private"

    approved = client.post(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/approve"
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "active"
    assert approved.json()["avatar_id"].startswith("wav2lip256_idle_p_")
    assert approved.json()["avatar_id"].endswith("_cropv2")
    assert client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation"
    ).json()["status"] == "active"
    assert client.get("/api/v1/avatar/active").json()["avatar_id"] == approved.json()["avatar_id"]

    sequence = tmp_path / "approved-sequence"
    sequence.mkdir()
    sequence_files = {
        "intro": sequence / "intro.mp4",
        "idle": sequence / "idle.mp4",
        "outro": sequence / "outro.mp4",
    }
    for kind, path in sequence_files.items():
        path.write_bytes(f"approved-{kind}".encode())
    close_keyframe = sequence / "frontal.png"
    close_keyframe.write_bytes(b"approved-frontal")
    manifest = {
        "generation_mode": "direct_complete_scene_sequence",
        "matting": False,
        "close_keyframe": {
            "sha256": hashlib.sha256(close_keyframe.read_bytes()).hexdigest(),
        },
    }
    for kind, path in sequence_files.items():
        manifest[kind] = {
            "path": str(path.resolve()),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    manifest_path = sequence / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="avatar.visual_approval_required"):
        service.install_approved_sequence(
            derivative_id,
            manifest_path=manifest_path,
            close_keyframe=close_keyframe,
            visually_approved=False,
        )

    tampered_manifest = sequence / "tampered-manifest.json"
    tampered = {**manifest, "idle": {**manifest["idle"], "sha256": "0" * 64}}
    tampered_manifest.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="avatar.sequence_output_mismatch"):
        service.install_approved_sequence(
            derivative_id,
            manifest_path=tampered_manifest,
            close_keyframe=close_keyframe,
            visually_approved=True,
        )

    installed = service.install_approved_sequence(
        derivative_id,
        manifest_path=manifest_path,
        close_keyframe=close_keyframe,
        visually_approved=True,
    )
    assert installed["has_sequence_previews"] is True
    assert installed["has_intro_preview"] is True
    assert installed["has_outro_preview"] is True
    assert installed["sequence_version"].startswith("ux13-frontal-")
    assert installed["single_surface_ready"] is True
    assert installed["speaking_avatar_id"].endswith("_scenev1")
    assert client.get("/api/v1/avatar/active").json()["avatar_id"] == installed["speaking_avatar_id"]
    assert client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/intro"
    ).content == b"approved-intro"
    assert client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/video"
    ).content == b"approved-idle"
    assert client.get(
        f"/api/v1/avatar-builds/{derivative_id}/idle-generation/outro"
    ).content == b"approved-outro"
