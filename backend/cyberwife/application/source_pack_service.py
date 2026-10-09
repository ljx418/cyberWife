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

    def register_scenes(self, scenes: list[dict]) -> SourcePackManifest:
        """Idempotently register the trusted scene catalog using manifest CAS."""
        current = self._repository.load()
        if current is None:
            raise ValueError("source_pack.required")
        normalized = sorted(
            ({
                "scene_id": str(item["scene_id"]),
                "label": str(item["label"]),
                "asset_sha256": str(item["asset_sha256"]).lower(),
            } for item in scenes),
            key=lambda item: item["scene_id"],
        )
        existing = sorted(current.payload["scenes"], key=lambda item: item["scene_id"])
        if existing == normalized:
            return current
        payload = current.to_dict()
        payload["revision"] = current.revision + 1
        payload["scenes"] = normalized
        active_scene_id = payload.get("active_scene_id")
        if active_scene_id is not None and active_scene_id not in {item["scene_id"] for item in normalized}:
            raise ValueError("scene.active_reference_missing")
        manifest = SourcePackManifest.from_dict(payload)
        staged_sha256 = self._repository.stage(manifest)
        return self._repository.commit(
            expected_revision=current.revision,
            staged_sha256=staged_sha256,
        )

    def register_renditions(self, renditions: list[dict]) -> SourcePackManifest:
        """Replace the trusted rendition catalog idempotently using manifest CAS."""
        current = self._repository.load()
        if current is None:
            raise ValueError("source_pack.required")
        normalized = sorted(
            ({
                "rendition_id": str(item["rendition_id"]),
                "kind": str(item["kind"]),
                "source_ids": sorted(str(value) for value in item["source_ids"]),
                "scene_id": str(item["scene_id"]),
                "status": str(item["status"]),
                "sha256": str(item["sha256"]).lower(),
            } for item in renditions),
            key=lambda item: item["rendition_id"],
        )
        existing = sorted(
            ({**item, "source_ids": sorted(item["source_ids"])} for item in current.payload["renditions"]),
            key=lambda item: item["rendition_id"],
        )
        if existing == normalized:
            return current
        payload = current.to_dict()
        payload["revision"] = current.revision + 1
        payload["renditions"] = normalized
        manifest = SourcePackManifest.from_dict(payload)
        staged_sha256 = self._repository.stage(manifest)
        return self._repository.commit(
            expected_revision=current.revision,
            staged_sha256=staged_sha256,
        )

    def register_combinations(
        self,
        *,
        appearances: list[dict],
        renditions: list[dict],
        active_appearance_id: str,
    ) -> SourcePackManifest:
        """Atomically register approved X3.5 appearances and their renditions."""
        current = self._repository.load()
        if current is None:
            raise ValueError("source_pack.required")
        payload = current.to_dict()
        payload["revision"] = current.revision + 1
        payload["appearances"] = sorted(
            ({
                "appearance_id": str(item["appearance_id"]),
                "source_ids": sorted(str(value) for value in item["source_ids"]),
                "confirmed": bool(item["confirmed"]),
            } for item in appearances),
            key=lambda item: item["appearance_id"],
        )
        payload["renditions"] = sorted(
            ({
                "rendition_id": str(item["rendition_id"]),
                "kind": str(item["kind"]),
                "source_ids": sorted(str(value) for value in item["source_ids"]),
                "scene_id": str(item["scene_id"]),
                "status": str(item["status"]),
                "sha256": str(item["sha256"]).lower(),
            } for item in renditions),
            key=lambda item: item["rendition_id"],
        )
        payload["active_appearance_id"] = str(active_appearance_id)
        manifest = SourcePackManifest.from_dict(payload)
        selected = next(
            (item for item in manifest.payload["appearances"] if item["appearance_id"] == active_appearance_id),
            None,
        )
        if selected is None or selected["confirmed"] is not True:
            raise ValueError("appearance.not_confirmed")
        comparable = manifest.to_dict()
        comparable["revision"] = current.revision
        if comparable == current.to_dict():
            return current
        staged_sha256 = self._repository.stage(manifest)
        return self._repository.commit(
            expected_revision=current.revision,
            staged_sha256=staged_sha256,
        )

    def activate_combination(
        self,
        scene_id: str,
        appearance_id: str,
        *,
        rendition_ids: tuple[str, str],
        expected_revision: int,
    ) -> SourcePackManifest:
        """Atomically select one approved appearance+scene rendition pair."""
        current = self._repository.load()
        if current is None:
            raise ValueError("source_pack.required")
        if current.revision != expected_revision:
            from cyberwife.ports.assets import ManifestRevisionConflict
            raise ManifestRevisionConflict(
                f"expected revision {expected_revision}, current revision {current.revision}"
            )
        appearance = next(
            (item for item in current.payload["appearances"] if item["appearance_id"] == appearance_id),
            None,
        )
        if appearance is None or appearance["confirmed"] is not True:
            raise ValueError("appearance.not_confirmed")
        if scene_id not in {item["scene_id"] for item in current.payload["scenes"]}:
            raise ValueError("scene.not_found")
        selected = [
            item for item in current.payload["renditions"]
            if item["rendition_id"] in set(rendition_ids)
        ]
        if (
            len(selected) != 2
            or {item["kind"] for item in selected} != {"idle", "talking"}
            or any(item["scene_id"] != scene_id for item in selected)
            or any(item["status"] not in {"approved", "active"} for item in selected)
            or any(not set(item["source_ids"]).issubset(set(appearance["source_ids"])) for item in selected)
        ):
            raise ValueError("scene.renditions_incomplete")
        if (
            current.payload.get("active_scene_id") == scene_id
            and current.payload.get("active_appearance_id") == appearance_id
            and all(item["status"] == "active" for item in selected)
        ):
            return current
        payload = current.to_dict()
        payload["revision"] = current.revision + 1
        payload["active_scene_id"] = scene_id
        payload["active_appearance_id"] = appearance_id
        selected_ids = set(rendition_ids)
        for item in payload["renditions"]:
            if item["kind"] in {"idle", "talking"} and item["status"] in {"approved", "active"}:
                item["status"] = "active" if item["rendition_id"] in selected_ids else "approved"
        manifest = SourcePackManifest.from_dict(payload)
        staged_sha256 = self._repository.stage(manifest)
        return self._repository.commit(
            expected_revision=current.revision,
            staged_sha256=staged_sha256,
        )

    def activate_scene(self, scene_id: str, *, expected_revision: int) -> SourcePackManifest:
        """Atomically select a scene only when approved idle and talking assets exist."""
        current = self._repository.load()
        if current is None:
            raise ValueError("source_pack.required")
        if current.revision != expected_revision:
            from cyberwife.ports.assets import ManifestRevisionConflict
            raise ManifestRevisionConflict(
                f"expected revision {expected_revision}, current revision {current.revision}"
            )
        if scene_id not in {item["scene_id"] for item in current.payload["scenes"]}:
            raise ValueError("scene.not_found")
        approved = {
            item["kind"] for item in current.payload["renditions"]
            if item["scene_id"] == scene_id and item["status"] in {"approved", "active"}
        }
        if not {"idle", "talking"}.issubset(approved):
            raise ValueError("scene.renditions_incomplete")
        if current.payload.get("active_scene_id") == scene_id:
            return current
        payload = current.to_dict()
        payload["revision"] = current.revision + 1
        payload["active_scene_id"] = scene_id
        for item in payload["renditions"]:
            if item["kind"] in {"idle", "talking"}:
                item["status"] = "active" if item["scene_id"] == scene_id else "approved"
        manifest = SourcePackManifest.from_dict(payload)
        staged_sha256 = self._repository.stage(manifest)
        return self._repository.commit(
            expected_revision=current.revision,
            staged_sha256=staged_sha256,
        )
