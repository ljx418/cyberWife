from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cyberwife.application.scene_preset_service import DEFAULT_SCENES, ScenePresetService
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository
from ops import install_scene_renditions


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_installer_registers_four_complete_scene_pairs_idempotently(tmp_path, monkeypatch):
    data_root = tmp_path / "private"
    assets_root = data_root / "assets"
    portrait = assets_root / "portrait" / "source.png"
    portrait.parent.mkdir(parents=True)
    portrait.write_bytes(b"approved-identity")
    repository = JsonManifestRepository(data_root)
    source_pack = SourcePackService(repository)
    source_pack.add_source(
        sha256=sha(portrait), relative_path="portrait/source.png", angle="front",
        appearance_label="approved", consent_id="consent-1",
    )
    backgrounds = tmp_path / "backgrounds"
    backgrounds.mkdir()
    for definition in DEFAULT_SCENES:
        (backgrounds / definition.filename).write_bytes(definition.slug.encode())

    default_video = tmp_path / "default.mp4"
    default_video.write_bytes(b"default-approved-idle")
    default_avatar_id = "wav2lip256_default_scenev1"
    default_avatar = data_root / "avatar" / "avatars" / default_avatar_id
    default_avatar.mkdir(parents=True)
    (default_avatar / "manifest.json").write_text(json.dumps({
        "avatar_id": default_avatar_id, "source_sha256": sha(portrait),
        "idle_video_sha256": sha(default_video), "presentation": "complete_scene",
        "visual_approved": True, "frame_count": 160,
        "frame_size": [768, 432], "coordinates": [80, 320, 100, 300],
    }), encoding="utf-8")
    default_job = tmp_path / "job.json"
    default_job.write_text(json.dumps({
        "video_path": str(default_video), "speaking_avatar_id": default_avatar_id,
    }), encoding="utf-8")

    records = {}
    for definition in DEFAULT_SCENES:
        if definition.slug == "blue-hour-living":
            continue
        video = tmp_path / f"{definition.slug}.mp4"
        video.write_bytes(f"approved-{definition.slug}".encode())
        records[definition.slug] = {"output": str(video), "output_sha256": sha(video)}
    generated = tmp_path / "generated.json"
    generated.write_text(json.dumps({
        "generation_mode": "direct_complete_scene", "matting": False,
        "records": records,
    }), encoding="utf-8")

    builds = []
    def fake_build(
        source, idle, output_root, avatar_id, *,
        preserve_frame, target_fps, blend_profile,
    ):
        assert preserve_frame is True
        assert target_fps == 25.0
        assert blend_profile == "mouth_oval_v1"
        builds.append(avatar_id)
        target = output_root / avatar_id
        target.mkdir(parents=True)
        (target / "manifest.json").write_text(json.dumps({
            "avatar_id": avatar_id, "source_sha256": sha(source),
            "idle_video_sha256": sha(idle), "presentation": "complete_scene",
            "frame_count": 250, "frame_size": [768, 432],
            "runtime_fps": 25.0, "temporal_resample": "linear",
            "blend_profile": "mouth_oval_v1",
            "coordinates": [80, 320, 100, 300],
        }), encoding="utf-8")
        return target
    monkeypatch.setattr(install_scene_renditions, "build", fake_build)

    args = dict(
        data_root=data_root, assets_root=assets_root, backgrounds_root=backgrounds,
        generated_manifest_path=generated, default_job_path=default_job,
    )
    first = install_scene_renditions.install(**args)
    second = install_scene_renditions.install(**args)

    assert first["result"] == second["result"] == "PASS"
    assert first["revision"] == second["revision"] == 3
    assert len(first["bindings"]) == 4
    assert len(builds) == 4
    assert all(avatar_id.endswith("_scenev2_mouth") for avatar_id in builds)
    manifest = source_pack.load()
    assert manifest is not None and len(manifest.payload["renditions"]) == 8
    catalog = ScenePresetService(
        source_pack, backgrounds,
        binding_root=data_root / "v2x" / "scene-renditions",
        avatar_root=data_root / "avatar" / "avatars",
    ).ensure_registered()
    assert all(item["can_activate"] for item in catalog["items"])
