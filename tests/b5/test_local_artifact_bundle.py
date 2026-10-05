import json
import os
import pickle
import struct
import wave
from pathlib import Path

import pytest
import yaml

from ops.acceptance.prepare_local_artifacts import REQUIRED_MODELS, prepare, sha256_file, verify_published


def _wav(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(struct.pack("<h", 500) * 1600)


def _fixture(tmp_path: Path, repo_root: Path) -> Path:
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    models = {}
    for index, logical_id in enumerate(REQUIRED_MODELS):
        if logical_id in {"qwen3-14b-instruct-q4_k_m", "livetalking-wav2lip256", "silero-vad-v5"}:
            path = artifacts / f"model-{index}.bin"
            path.write_bytes(logical_id.encode())
            models[logical_id] = {"path": str(path), "kind": "file", "sha256": sha256_file(path), "license_accepted": True}
        else:
            path = artifacts / f"model-{index}"
            path.mkdir()
            models[logical_id] = {"path": str(path), "kind": "directory", "license_accepted": True}
    source = artifacts / "CosyVoice"
    source.mkdir()
    os.symlink("optional-training-data", source / "optional-data")
    voice = artifacts / "reference.wav"
    _wav(voice)
    avatar_id = "wav2lip256_bootstrap"
    avatar = artifacts / avatar_id
    (avatar / "full_imgs").mkdir(parents=True)
    (avatar / "face_imgs").mkdir()
    (avatar / "full_imgs/00000000.png").write_bytes(b"png")
    (avatar / "face_imgs/00000000.png").write_bytes(b"png")
    with (avatar / "coords.pkl").open("wb") as output:
        pickle.dump([(1, 2, 3, 4)], output)
    (avatar / "manifest.json").write_text(json.dumps({"avatar_id": avatar_id}), encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "format": "cyberwife-local-artifacts",
        "models": models,
        "cosyvoice_source": {"path": str(source), "license_accepted": True},
        "bootstrap": {
            "voice": {"path": str(voice), "transcript": "这是经过授权的测试声音。", "sha256": sha256_file(voice), "consent": True},
            "avatar": {"path": str(avatar), "avatar_id": avatar_id, "consent": True},
        },
    }
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_local_bundle_publishes_registry_and_private_bootstrap(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    source_example = Path(__file__).resolve().parents[2] / "config/model-registry.example.yaml"
    (repo / "config/model-registry.example.yaml").write_bytes(source_example.read_bytes())
    manifest = _fixture(tmp_path, repo)
    report = prepare(manifest, repo, tmp_path / "data", tmp_path / "report.json")
    registry = yaml.safe_load((repo / "config/model-registry.local.yaml").read_text(encoding="utf-8"))
    paths = {entry["logical_id"]: entry.get("absolute_path") for entry in registry["models"]}
    assert all(paths[logical_id] for logical_id in REQUIRED_MODELS)
    assert (tmp_path / "data/bootstrap/voice/reference.wav").is_file()
    assert (tmp_path / "data/avatar/avatars/wav2lip256_bootstrap/coords.pkl").is_file()
    assert (tmp_path / "data/src/CosyVoice").is_dir()
    assert (tmp_path / "data/bootstrap/avatar-id").read_text().strip() == "wav2lip256_bootstrap"
    assert report["stores_private_paths"] is False and report["stores_transcript"] is False
    assert verify_published(repo, tmp_path / "data")["result"] == "PASS"


def test_local_bundle_rejects_missing_consent_without_publishing(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    source_example = Path(__file__).resolve().parents[2] / "config/model-registry.example.yaml"
    (repo / "config/model-registry.example.yaml").write_bytes(source_example.read_bytes())
    manifest = _fixture(tmp_path, repo)
    document = json.loads(manifest.read_text())
    document["bootstrap"]["voice"]["consent"] = False
    manifest.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="explicit consent"):
        prepare(manifest, repo, tmp_path / "data", tmp_path / "report.json")
    assert not (repo / "config/model-registry.local.yaml").exists()
    assert not (tmp_path / "data/bootstrap").exists()


def test_local_bundle_upgrade_preserves_verified_metadata(tmp_path: Path):
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    source_example = Path(__file__).resolve().parents[2] / "config/model-registry.example.yaml"
    existing = yaml.safe_load(source_example.read_text(encoding="utf-8"))
    for entry in existing["models"]:
        if entry["logical_id"] in REQUIRED_MODELS:
            entry["status"] = "verified"
            entry["verified_at"] = "2026-01-01T00:00:00Z"
    (repo / "config/model-registry.local.yaml").write_text(
        yaml.safe_dump(existing, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    manifest = _fixture(tmp_path, repo)
    prepare(manifest, repo, tmp_path / "data", tmp_path / "report.json")
    updated = yaml.safe_load((repo / "config/model-registry.local.yaml").read_text(encoding="utf-8"))
    required = [entry for entry in updated["models"] if entry["logical_id"] in REQUIRED_MODELS]
    assert len(required) == 7
    assert all(entry["status"] == "verified" for entry in required)
    assert all(entry["verified_at"] == "2026-01-01T00:00:00Z" for entry in required)
