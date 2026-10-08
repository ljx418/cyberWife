"""Application orchestration for the dormant V2-X source-pack contract."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid5

from cyberwife.domain.source_pack import SourcePackManifest
from cyberwife.ports.assets import ExperienceManifestRepository


_PACK_NAMESPACE = UUID("1e46d362-608d-4d62-867f-fb43519746c1")
_SOURCE_NAMESPACE = UUID("e77e6bfa-0b68-4e8d-bc30-600b97af85e2")


class SourcePackService:
    def __init__(self, repository: ExperienceManifestRepository) -> None:
        self._repository = repository

    def bootstrap_from_v1(
        self,
        *,
        legacy_asset_id: int,
        sha256: str,
        relative_path: str,
        consent_id: str,
        created_at: str | None = None,
    ) -> SourcePackManifest:
        current = self._repository.load()
        if current is not None:
            if current.payload.get("legacy_asset_id") != legacy_asset_id:
                raise ValueError("manifest already belongs to another legacy asset")
            return current
        pack_id = str(uuid5(_PACK_NAMESPACE, f"legacy-portrait:{legacy_asset_id}"))
        source_id = str(uuid5(_SOURCE_NAMESPACE, f"legacy-portrait:{legacy_asset_id}:{sha256.lower()}"))
        manifest = SourcePackManifest.from_dict({
            "schema_version": 1,
            "pack_id": pack_id,
            "revision": 1,
            "legacy_asset_id": legacy_asset_id,
            "active_appearance_id": None,
            "active_scene_id": None,
            "sources": [{
                "source_id": source_id,
                "sha256": sha256,
                "relative_path": relative_path,
                "angle": "front",
                "appearance_label": "V1已确认人物素材",
                "consent_id": consent_id,
                "provenance": "v1_active_asset",
                "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            }],
            "appearances": [],
            "scenes": [],
            "renditions": [],
        })
        staged_sha256 = self._repository.stage(manifest)
        return self._repository.commit(expected_revision=None, staged_sha256=staged_sha256)
