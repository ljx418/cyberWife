"""Application orchestration for the dormant V2-X source-pack contract."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4, uuid5

from cyberwife.domain.source_pack import SourcePackManifest
from cyberwife.ports.assets import ExperienceManifestRepository


_PACK_NAMESPACE = UUID("1e46d362-608d-4d62-867f-fb43519746c1")
_SOURCE_NAMESPACE = UUID("e77e6bfa-0b68-4e8d-bc30-600b97af85e2")


class SourcePackService:
    def __init__(self, repository: ExperienceManifestRepository) -> None:
        self._repository = repository

    def load(self) -> SourcePackManifest | None:
        return self._repository.load()

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

    def add_source(
        self,
        *,
        sha256: str,
        relative_path: str,
        angle: str,
        appearance_label: str,
        consent_id: str,
        provenance: str = "local_upload",
        created_at: str | None = None,
    ) -> tuple[SourcePackManifest, dict, bool]:
        """Append one source with a revision CAS; identical bytes are idempotent."""
        current = self._repository.load()
        if current is not None:
            existing = next(
                (item for item in current.payload["sources"] if item["sha256"] == sha256.lower()),
                None,
            )
            if existing is not None:
                return current, dict(existing), False
            payload = current.to_dict()
            payload["revision"] = current.revision + 1
            expected_revision: int | None = current.revision
            pack_id = str(payload["pack_id"])
        else:
            pack_id = str(uuid4())
            payload = {
                "schema_version": 1,
                "pack_id": pack_id,
                "revision": 1,
                "legacy_asset_id": None,
                "active_appearance_id": None,
                "active_scene_id": None,
                "sources": [],
                "appearances": [],
                "scenes": [],
                "renditions": [],
            }
            expected_revision = None
        source_id = str(uuid5(_SOURCE_NAMESPACE, f"source-pack:{pack_id}:{sha256.lower()}"))
        source = {
            "source_id": source_id,
            "sha256": sha256.lower(),
            "relative_path": relative_path,
            "angle": angle,
            "appearance_label": appearance_label,
            "consent_id": consent_id,
            "provenance": provenance,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        }
        payload["sources"].append(source)
        manifest = SourcePackManifest.from_dict(payload)
        staged_sha256 = self._repository.stage(manifest)
        committed = self._repository.commit(
            expected_revision=expected_revision,
            staged_sha256=staged_sha256,
        )
        return committed, dict(source), True
