"""V2-X single-active-character source-pack manifest domain contract."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ANGLES = {"front", "left", "right", "full_body", "unknown"}
_RENDITION_KINDS = {"idle", "micro_action", "talking"}
_RENDITION_STATES = {"staged", "approved", "active", "rejected"}


def _uuid(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{field} must be a UUID") from exc


def _sha(value: Any, field: str) -> str:
    normalized = str(value).lower()
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{field} must be a lowercase SHA-256")
    return normalized


def _relative_path(value: Any, field: str) -> str:
    raw = str(value)
    path = PurePosixPath(raw)
    if (
        not raw
        or "\\" in raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or any(ord(char) < 32 for char in raw)
    ):
        raise ValueError(f"{field} must be a safe POSIX relative path")
    return raw


def _text(value: Any, field: str, *, maximum: int = 120) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > maximum or any(ord(char) < 32 for char in normalized):
        raise ValueError(f"{field} is invalid")
    return normalized


def _unique_ids(items: list[dict[str, Any]], field: str) -> set[str]:
    values = [item[field] for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {field}")
    return set(values)


@dataclass(frozen=True)
class SourcePackManifest:
    """Validated immutable manifest; V2-X deliberately has no character_id."""

    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SourcePackManifest":
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("schema_version must be 1")
        revision = raw.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("revision must be a positive integer")
        allowed = {
            "schema_version", "pack_id", "revision", "legacy_asset_id",
            "active_appearance_id", "active_scene_id", "sources", "appearances",
            "scenes", "renditions",
        }
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown manifest fields: {sorted(unknown)}")
        payload: dict[str, Any] = {
            "schema_version": 1,
            "pack_id": _uuid(raw.get("pack_id"), "pack_id"),
            "revision": revision,
            "legacy_asset_id": raw.get("legacy_asset_id"),
            "active_appearance_id": None,
            "active_scene_id": None,
            "sources": [],
            "appearances": [],
            "scenes": [],
            "renditions": [],
        }
        legacy = payload["legacy_asset_id"]
        if legacy is not None and (not isinstance(legacy, int) or isinstance(legacy, bool) or legacy < 1):
            raise ValueError("legacy_asset_id must be a positive integer or null")

        for collection in ("sources", "appearances", "scenes", "renditions"):
            if not isinstance(raw.get(collection, []), list):
                raise ValueError(f"{collection} must be an array")

        for index, item in enumerate(raw.get("sources", [])):
            if not isinstance(item, dict):
                raise ValueError(f"sources[{index}] must be an object")
            expected = {"source_id", "sha256", "relative_path", "angle", "appearance_label", "consent_id", "provenance", "created_at"}
            if set(item) != expected:
                raise ValueError(f"sources[{index}] fields are invalid")
            angle = str(item.get("angle"))
            if angle not in _ANGLES:
                raise ValueError(f"sources[{index}].angle is invalid")
            created_at = str(item.get("created_at"))
            try:
                observed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if observed.tzinfo is None:
                    raise ValueError
            except ValueError as exc:
                raise ValueError(f"sources[{index}].created_at must be RFC3339") from exc
            payload["sources"].append({
                "source_id": _uuid(item.get("source_id"), f"sources[{index}].source_id"),
                "sha256": _sha(item.get("sha256"), f"sources[{index}].sha256"),
                "relative_path": _relative_path(item.get("relative_path"), f"sources[{index}].relative_path"),
                "angle": angle,
                "appearance_label": _text(item.get("appearance_label"), f"sources[{index}].appearance_label"),
                "consent_id": _text(item.get("consent_id"), f"sources[{index}].consent_id"),
                "provenance": _text(item.get("provenance"), f"sources[{index}].provenance"),
                "created_at": created_at,
            })
        source_ids = _unique_ids(payload["sources"], "source_id")

        for index, item in enumerate(raw.get("appearances", [])):
            if not isinstance(item, dict) or set(item) != {"appearance_id", "source_ids", "confirmed"}:
                raise ValueError(f"appearances[{index}] fields are invalid")
            if not isinstance(item.get("source_ids"), list) or not isinstance(item.get("confirmed"), bool):
                raise ValueError(f"appearances[{index}] types are invalid")
            source_refs = [_uuid(value, f"appearances[{index}].source_ids") for value in item.get("source_ids", [])]
            if not source_refs or not set(source_refs).issubset(source_ids):
                raise ValueError(f"appearances[{index}] has missing source references")
            payload["appearances"].append({
                "appearance_id": _uuid(item.get("appearance_id"), f"appearances[{index}].appearance_id"),
                "source_ids": source_refs,
                "confirmed": item["confirmed"],
            })
        appearance_ids = _unique_ids(payload["appearances"], "appearance_id")

        for index, item in enumerate(raw.get("scenes", [])):
            if not isinstance(item, dict) or set(item) != {"scene_id", "label", "asset_sha256"}:
                raise ValueError(f"scenes[{index}] fields are invalid")
            payload["scenes"].append({
                "scene_id": _uuid(item.get("scene_id"), f"scenes[{index}].scene_id"),
                "label": _text(item.get("label"), f"scenes[{index}].label"),
                "asset_sha256": _sha(item.get("asset_sha256"), f"scenes[{index}].asset_sha256"),
            })
        scene_ids = _unique_ids(payload["scenes"], "scene_id")

        for index, item in enumerate(raw.get("renditions", [])):
            if not isinstance(item, dict) or set(item) != {"rendition_id", "kind", "source_ids", "scene_id", "status", "sha256"}:
                raise ValueError(f"renditions[{index}] fields are invalid")
            if not isinstance(item.get("source_ids"), list):
                raise ValueError(f"renditions[{index}].source_ids must be an array")
            kind, status = str(item.get("kind")), str(item.get("status"))
            if kind not in _RENDITION_KINDS or status not in _RENDITION_STATES:
                raise ValueError(f"renditions[{index}] kind/status is invalid")
            source_refs = [_uuid(value, f"renditions[{index}].source_ids") for value in item.get("source_ids", [])]
            scene_id = _uuid(item.get("scene_id"), f"renditions[{index}].scene_id")
            if not source_refs or not set(source_refs).issubset(source_ids) or scene_id not in scene_ids:
                raise ValueError(f"renditions[{index}] has missing references")
            payload["renditions"].append({
                "rendition_id": _uuid(item.get("rendition_id"), f"renditions[{index}].rendition_id"),
                "kind": kind,
                "source_ids": source_refs,
                "scene_id": scene_id,
                "status": status,
                "sha256": _sha(item.get("sha256"), f"renditions[{index}].sha256"),
            })
        _unique_ids(payload["renditions"], "rendition_id")

        for field, allowed_ids in (("active_appearance_id", appearance_ids), ("active_scene_id", scene_ids)):
            value = raw.get(field)
            if value is not None:
                normalized = _uuid(value, field)
                if normalized not in allowed_ids:
                    raise ValueError(f"{field} references a missing entity")
                payload[field] = normalized
        return cls(payload)

    @property
    def revision(self) -> int:
        return int(self.payload["revision"])

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.payload,
            "sources": [dict(item) for item in self.payload["sources"]],
            "appearances": [{**item, "source_ids": list(item["source_ids"])} for item in self.payload["appearances"]],
            "scenes": [dict(item) for item in self.payload["scenes"]],
            "renditions": [{**item, "source_ids": list(item["source_ids"])} for item in self.payload["renditions"]],
        }
