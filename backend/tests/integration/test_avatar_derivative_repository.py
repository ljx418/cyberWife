"""UX1: a visible portrait and realtime Avatar must switch atomically."""
from pathlib import Path

import pytest

from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[3]


def _asset(repo: SqliteRepository, suffix: str) -> dict:
    return repo.create_asset_version({
        "kind": "portrait",
        "relative_path": f"portrait/{suffix}.png",
        "sha256": suffix * 64,
        "size_bytes": 123,
        "filename_or_revision": f"{suffix}.png",
    })


def _ready(repo: SqliteRepository, asset: dict, suffix: str) -> dict:
    row = repo.create_avatar_derivative(
        asset["id"], engine="wav2lip", avatar_id=f"wav2lip256_p_{suffix * 16}"
    )
    return repo.update_avatar_derivative(
        row["id"],
        status="ready",
        manifest={"frame_count": 1, "source_sha256": asset["sha256"]},
    )


def test_activate_and_restore_keep_source_identity(tmp_path):
    repo = SqliteRepository(tmp_path / "ux1.db", ROOT / "migrations" / "0001_init.sql")
    repo.grant_consent("portrait", "v1")
    first = _asset(repo, "a")
    second = _asset(repo, "b")
    first_build = _ready(repo, first, "a")
    second_build = _ready(repo, second, "b")

    repo.activate_avatar_derivative(first_build["id"])
    active = repo.activate_avatar_derivative(second_build["id"])
    assert active["asset_id"] == second["id"]
    assert active["source_sha256"] == second["sha256"]

    restored = repo.restore_previous_avatar_derivative()
    assert restored["asset_id"] == first["id"]
    assert repo.get_active_asset("portrait")["sha256"] == restored["source_sha256"]


def test_activation_rolls_back_both_pointers_on_fault(tmp_path):
    repo = SqliteRepository(tmp_path / "ux1.db", ROOT / "migrations" / "0001_init.sql")
    repo.grant_consent("portrait", "v1")
    first = _asset(repo, "c")
    second = _asset(repo, "d")
    first_build = _ready(repo, first, "c")
    second_build = _ready(repo, second, "d")
    repo.activate_avatar_derivative(first_build["id"])

    def fail(point: str) -> None:
        if point == "after_archive":
            raise RuntimeError("injected")

    with pytest.raises(RuntimeError, match="injected"):
        repo.activate_avatar_derivative(second_build["id"], fault_injector=fail)
    active = repo.get_active_avatar_derivative()
    assert active is not None
    assert active["id"] == first_build["id"]
    assert repo.get_active_asset("portrait")["id"] == first["id"]


def test_revoking_portrait_consent_removes_both_active_pointers(tmp_path):
    repo = SqliteRepository(tmp_path / "ux1.db", ROOT / "migrations" / "0001_init.sql")
    repo.grant_consent("portrait", "v1")
    asset = _asset(repo, "e")
    build = _ready(repo, asset, "e")
    repo.activate_avatar_derivative(build["id"])
    repo.revoke_consent("portrait")
    assert repo.get_active_asset("portrait") is None
    assert repo.get_active_avatar_derivative() is None


def test_idle_artifact_requires_visual_approval_and_matching_source(tmp_path):
    repo = SqliteRepository(tmp_path / "ux1.db", ROOT / "migrations" / "0001_init.sql")
    asset = _asset(repo, "f")
    build = _ready(repo, asset, "f")
    manifest = {"source_sha256": asset["sha256"], "frame_count": 81}
    with pytest.raises(ValueError, match="visual_approval"):
        repo.promote_avatar_derivative_artifact(
            build["id"], avatar_id="wav2lip256_idle_p_f", manifest=manifest
        )
    manifest["visual_approved"] = True
    promoted = repo.promote_avatar_derivative_artifact(
        build["id"], avatar_id="wav2lip256_idle_p_f", manifest=manifest
    )
    assert promoted["status"] == "ready"
    assert promoted["avatar_id"] == "wav2lip256_idle_p_f"


def test_duplicate_build_claim_has_single_winner(tmp_path):
    repo = SqliteRepository(tmp_path / "ux1.db", ROOT / "migrations" / "0001_init.sql")
    asset = _asset(repo, "g")
    row = repo.create_avatar_derivative(
        asset["id"], engine="wav2lip", avatar_id="wav2lip256_p_g"
    )
    assert repo.claim_avatar_derivative_build(row["id"])["status"] == "building"
    assert repo.claim_avatar_derivative_build(row["id"]) is None


def test_promoting_active_idle_artifact_keeps_active_pointer_visible(tmp_path):
    repo = SqliteRepository(tmp_path / "ux1.db", ROOT / "migrations" / "0001_init.sql")
    repo.grant_consent("portrait", "v1")
    asset = _asset(repo, "h")
    build = _ready(repo, asset, "h")
    repo.activate_avatar_derivative(build["id"])
    promoted = repo.promote_avatar_derivative_artifact(
        build["id"],
        avatar_id="wav2lip256_idle_p_h",
        manifest={"source_sha256": asset["sha256"], "visual_approved": True},
    )
    assert promoted["status"] == "active"
    assert repo.get_active_avatar_derivative()["avatar_id"] == "wav2lip256_idle_p_h"
