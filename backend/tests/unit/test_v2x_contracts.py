from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from cyberwife.application.runtime_config import V2X_FEATURE_FLAGS, load_runtime_config
from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.application.v2x_evidence import contract_evidence
from cyberwife.domain.source_pack import SourcePackManifest
from cyberwife.infrastructure.json_manifest_repository import (
    JsonManifestRepository,
    ManifestRevisionConflict,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SHA_A = "a" * 64
SHA_B = "b" * 64


def manifest(revision: int = 1) -> SourcePackManifest:
    source_id, appearance_id, scene_id, rendition_id = [str(uuid4()) for _ in range(4)]
    return SourcePackManifest.from_dict({
        "schema_version": 1,
        "pack_id": str(uuid4()),
        "revision": revision,
        "legacy_asset_id": 7,
        "active_appearance_id": appearance_id,
        "active_scene_id": scene_id,
        "sources": [{
            "source_id": source_id,
            "sha256": SHA_A,
            "relative_path": "portrait/approved.png",
            "angle": "front",
            "appearance_label": "已确认红色上衣",
            "consent_id": "consent-7",
            "provenance": "upload",
            "created_at": "2026-10-08T12:00:00+08:00",
        }],
        "appearances": [{"appearance_id": appearance_id, "source_ids": [source_id], "confirmed": True}],
        "scenes": [{"scene_id": scene_id, "label": "夜间客厅", "asset_sha256": SHA_B}],
        "renditions": [{
            "rendition_id": rendition_id,
            "kind": "idle",
            "source_ids": [source_id],
            "scene_id": scene_id,
            "status": "approved",
            "sha256": "c" * 64,
        }],
    })


def with_revision(value: SourcePackManifest, revision: int) -> SourcePackManifest:
    payload = value.to_dict()
    payload["revision"] = revision
    return SourcePackManifest.from_dict(payload)


def test_default_flags_only_enable_contracts():
    config = load_runtime_config(REPO_ROOT, REPO_ROOT / "config" / "not-present.toml")
    assert set(config["v2x"]) == set(V2X_FEATURE_FLAGS)
    assert config["v2x"]["contracts"] is True
    assert all(not value for key, value in config["v2x"].items() if key != "contracts")


@pytest.mark.parametrize("toml", ["[v2x]\nsource_pack='yes'\n", "[v2x]\nunknown=true\n"])
def test_invalid_v2x_configuration_is_rejected(tmp_path, toml):
    local = tmp_path / "runtime.toml"
    local.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match="v2x"):
        load_runtime_config(REPO_ROOT, local)


@pytest.mark.parametrize("path", ["../private.png", "/tmp/private.png", r"portrait\private.png"])
def test_manifest_rejects_unsafe_paths(path):
    payload = manifest().to_dict()
    payload["sources"][0]["relative_path"] = path
    with pytest.raises(ValueError, match="relative path"):
        SourcePackManifest.from_dict(payload)


def test_manifest_rejects_duplicate_and_missing_references():
    payload = manifest().to_dict()
    payload["sources"].append(dict(payload["sources"][0]))
    with pytest.raises(ValueError, match="duplicate source_id"):
        SourcePackManifest.from_dict(payload)


@pytest.mark.parametrize("field", ["sources", "appearances", "scenes", "renditions"])
def test_manifest_rejects_non_array_collections(field):
    payload = manifest().to_dict()
    payload[field] = {}
    with pytest.raises(ValueError, match="array"):
        SourcePackManifest.from_dict(payload)


def test_manifest_rejects_unknown_nested_fields_and_naive_time():
    payload = manifest().to_dict()
    payload["sources"][0]["private_note"] = "must not be silently accepted"
    with pytest.raises(ValueError, match="fields"):
        SourcePackManifest.from_dict(payload)
    payload = manifest().to_dict()
    payload["sources"][0]["created_at"] = "2026-10-08T12:00:00"
    with pytest.raises(ValueError, match="RFC3339"):
        SourcePackManifest.from_dict(payload)
    payload = manifest().to_dict()
    payload["renditions"][0]["source_ids"] = [str(uuid4())]
    with pytest.raises(ValueError, match="missing references"):
        SourcePackManifest.from_dict(payload)


def test_atomic_commit_conflict_and_exact_rollback(tmp_path):
    repository = JsonManifestRepository(tmp_path)
    first = manifest(1)
    first_bytes = repository._encode(first)
    staged = repository.stage(first)
    assert repository.commit(expected_revision=None, staged_sha256=staged).revision == 1
    second = with_revision(first, 2)
    staged = repository.stage(second)
    with pytest.raises(ManifestRevisionConflict):
        repository.commit(expected_revision=99, staged_sha256=staged)
    assert repository.active_bytes() == first_bytes
    assert repository.commit(expected_revision=1, staged_sha256=staged).revision == 2
    restored = repository.rollback(1)
    assert restored.revision == 1
    assert repository.active_bytes() == first_bytes


def test_replace_failure_leaves_old_active_valid(tmp_path, monkeypatch):
    repository = JsonManifestRepository(tmp_path)
    first = manifest(1)
    staged = repository.stage(first)
    repository.commit(expected_revision=None, staged_sha256=staged)
    old_bytes = repository.active_bytes()
    staged = repository.stage(with_revision(first, 2))
    real_replace = __import__("os").replace

    def fail_staged(source, target):
        if Path(source).name == ".source-pack.v1.staged.json":
            raise OSError("injected replace failure")
        return real_replace(source, target)

    monkeypatch.setattr("cyberwife.infrastructure.json_manifest_repository.os.replace", fail_staged)
    with pytest.raises(OSError, match="injected"):
        repository.commit(expected_revision=1, staged_sha256=staged)
    assert repository.active_bytes() == old_bytes
    assert repository.load().revision == 1


def test_staged_writer_token_prevents_cross_writer_commit(tmp_path):
    repository = JsonManifestRepository(tmp_path)
    first = manifest(1)
    first_token = repository.stage(first)
    replacement = manifest(1)
    replacement_token = repository.stage(replacement)
    assert first_token != replacement_token
    with pytest.raises(ManifestRevisionConflict, match="another writer"):
        repository.commit(expected_revision=None, staged_sha256=first_token)
    assert repository.load() is None
    assert repository.commit(expected_revision=None, staged_sha256=replacement_token).revision == 1


def test_bootstrap_is_idempotent_and_uses_stable_ids(tmp_path):
    repository = JsonManifestRepository(tmp_path)
    service = SourcePackService(repository)
    first = service.bootstrap_from_v1(
        legacy_asset_id=42,
        sha256=SHA_A,
        relative_path="portrait/v1.png",
        consent_id="consent-42",
        created_at="2026-10-08T00:00:00Z",
    )
    second = service.bootstrap_from_v1(
        legacy_asset_id=42,
        sha256=SHA_A,
        relative_path="portrait/v1.png",
        consent_id="consent-42",
        created_at="2026-10-08T00:00:00Z",
    )
    assert second.to_dict() == first.to_dict()
    assert second.revision == 1


def test_evidence_excludes_private_values():
    value = manifest()
    evidence = contract_evidence({"contracts": True, "source_pack": False}, value)
    serialized = json.dumps(evidence, ensure_ascii=False)
    assert evidence["manifest"]["sources"] == 1
    assert len(evidence["manifest"]["sha256"]) == 64
    for private in ("夜间客厅", "已确认红色上衣", "portrait/approved.png", "consent-7"):
        assert private not in serialized
