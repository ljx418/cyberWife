"""Content-addressed portrait → LiveTalking Avatar build orchestration."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from cyberwife.infrastructure.asset_store import AssetStore


_SAFE_AVATAR_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class AvatarAssetService:
    """Build private Avatar data without exposing filesystem paths in the API."""

    def __init__(self, repository, *, assets_root: Path, avatar_root: Path) -> None:
        self._repository = repository
        self._store = AssetStore(assets_root)
        self._avatar_root = Path(avatar_root)

    @staticmethod
    def avatar_id(source_sha256: str, engine: str = "wav2lip") -> str:
        prefix = "wav2lip256" if engine == "wav2lip" else "musetalk15"
        value = f"{prefix}_p_{source_sha256[:16]}"
        if not _SAFE_AVATAR_ID.fullmatch(value):
            raise ValueError("avatar.invalid_id")
        return value

    def create_build(self, asset_id: int, *, engine: str = "wav2lip") -> dict:
        asset = self._repository.get_asset_version(asset_id)
        if asset is None or asset.get("kind") != "portrait":
            raise KeyError(asset_id)
        avatar_id = self.avatar_id(str(asset["sha256"]), engine)
        return self._repository.create_avatar_derivative(
            asset_id, engine=engine, avatar_id=avatar_id
        )

    def run_build(self, derivative_id: int) -> None:
        row = self._repository.claim_avatar_derivative_build(derivative_id)
        if row is None:
            return
        try:
            source = self._store.resolve(str(row["relative_path"]))
            if row["engine"] != "wav2lip":
                raise RuntimeError("avatar.engine_not_installed")
            # Import lazily so API-only tests do not require OpenCV.
            from ops.build_static_avatar import build

            target = build(source, self._avatar_root, str(row["avatar_id"]))
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("source_sha256") != row["source_sha256"]:
                raise RuntimeError("avatar.source_mismatch")
            manifest["manifest_sha256"] = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            self._repository.update_avatar_derivative(
                derivative_id, status="ready", manifest=manifest
            )
        except Exception as exc:
            code = str(exc).splitlines()[0][:120] or exc.__class__.__name__
            self._repository.update_avatar_derivative(
                derivative_id, status="failed", error_code=code
            )

    def promote_idle_video(
        self,
        derivative_id: int,
        idle_video: Path,
        *,
        visually_approved: bool,
    ) -> dict:
        """Build and stage a generated idle loop; never bypass visual approval."""
        if not visually_approved:
            raise ValueError("avatar.visual_approval_required")
        row = self._repository.get_avatar_derivative(derivative_id)
        if row is None:
            raise KeyError(derivative_id)
        source = self._store.resolve(str(row["relative_path"]))
        avatar_id = f"wav2lip256_idle_p_{str(row['source_sha256'])[:16]}"
        from ops.build_video_avatar import build

        target = build(source, Path(idle_video), self._avatar_root, avatar_id)
        manifest_path = target / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["visual_approved"] = True
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        manifest["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        return self._repository.promote_avatar_derivative_artifact(
            derivative_id,
            avatar_id=avatar_id,
            manifest=manifest,
        )

    def public_record(self, row: dict) -> dict:
        manifest = json.loads(row.get("manifest_json") or "{}")
        return {
            "id": int(row["id"]),
            "asset_id": int(row["asset_id"]),
            "engine": row["engine"],
            "avatar_id": row["avatar_id"],
            "source_sha256": row["source_sha256"],
            "status": row["status"],
            "frame_count": int(manifest.get("frame_count", 0)),
            "frame_size": manifest.get("frame_size"),
            "face_box": manifest.get("coordinates"),
            "error_code": row.get("error_code"),
            "updated_at": row["updated_at"],
        }
