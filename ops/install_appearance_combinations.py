#!/usr/bin/env python3
"""Install the human-approved X3.5 scene/appearance combination catalog."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import UUID, uuid5

from cyberwife.application.source_pack_service import SourcePackService
from cyberwife.infrastructure.json_manifest_repository import JsonManifestRepository


APPEARANCE_NAMESPACE = UUID("30a42e0b-8edf-4e8d-af98-48bcdf357b60")
RENDITION_NAMESPACE = UUID("92e615cd-881c-4a4d-901d-ddba0b4129e9")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(target: Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def _atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def _rendition_id(appearance_id: str, scene_id: str, kind: str, sha256: str) -> str:
    return str(uuid5(RENDITION_NAMESPACE, f"{appearance_id}:{scene_id}:{kind}:{sha256}"))


def install(*, data_root: Path, candidate_manifest_path: Path) -> dict:
    data_root = data_root.resolve()
    binding_root = data_root / "v2x" / "scene-renditions"
    avatar_root = data_root / "avatar" / "avatars"
    legacy_path = binding_root / "scene-bindings.v1.json"
    if not legacy_path.is_file():
        raise FileNotFoundError("scene.legacy_bindings_missing")
    legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_manifest_path.read_text(encoding="utf-8"))
    if (
        legacy.get("schema_version") != 1
        or candidate.get("schema_version") != 1
        or candidate.get("engine") != "musetalk"
        or candidate.get("presentation") != "complete_scene"
        or candidate.get("matting") is not False
        or candidate.get("visual_approval_required") is not True
    ):
        raise ValueError("combination.input_manifest_invalid")

    repository = JsonManifestRepository(data_root)
    source_pack = SourcePackService(repository)
    manifest = source_pack.load()
    if manifest is None or not manifest.payload["sources"]:
        raise ValueError("source_pack.required")
    source_sha = str(legacy.get("source_sha256", ""))
    source = next((item for item in manifest.payload["sources"] if item["sha256"] == source_sha), None)
    if source is None:
        raise ValueError("appearance.source_identity_missing")
    source_ids = [source["source_id"]]
    red_id = str(uuid5(APPEARANCE_NAMESPACE, f"{manifest.payload['pack_id']}:approved-red"))
    blue_id = str(candidate.get("appearance_id", ""))
    try:
        UUID(blue_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("appearance.id_invalid") from exc
    if len(candidate.get("records", {})) != 3:
        raise ValueError("combination.requires_three_secondary_scenes")
    active_appearance_id = manifest.payload.get("active_appearance_id")
    if active_appearance_id not in {red_id, blue_id}:
        active_appearance_id = red_id

    bindings: list[dict] = []
    renditions: list[dict] = []
    for item in legacy.get("bindings", []):
        idle = (binding_root / str(item.get("idle_relative_path", ""))).resolve()
        avatar_manifest = avatar_root / str(item.get("speaking_avatar_id", "")) / "manifest.json"
        if (
            binding_root not in idle.parents
            or avatar_root not in avatar_manifest.parents
            or not idle.is_file()
            or not avatar_manifest.is_file()
            or _sha256(idle) != item.get("idle_sha256")
            or _sha256(avatar_manifest) != item.get("talking_sha256")
        ):
            raise ValueError("combination.legacy_binding_invalid")
        enriched = {**item, "appearance_id": red_id, "appearance_label": "已批准红色针织上衣"}
        bindings.append(enriched)
        for kind, sha_field, id_field in (
            ("idle", "idle_sha256", "idle_rendition_id"),
            ("talking", "talking_sha256", "talking_rendition_id"),
        ):
            renditions.append({
                "rendition_id": str(item[id_field]) if item.get(id_field) else _rendition_id(red_id, item["scene_id"], kind, item[sha_field]),
                "kind": kind,
                "source_ids": source_ids,
                "scene_id": item["scene_id"],
                "status": "active" if (
                    active_appearance_id == red_id
                    and manifest.payload.get("active_scene_id") == item["scene_id"]
                ) else "approved",
                "sha256": item[sha_field],
            })

    pending_approvals: list[tuple[Path, dict]] = []
    for slug, record in sorted(candidate["records"].items()):
        if (
            record.get("appearance_id") != blue_id
            or record.get("status") != "staged"
            or not isinstance(record.get("scene_id"), str)
        ):
            raise ValueError(f"combination.candidate_record_invalid:{slug}")
        idle = Path(str(record.get("idle", ""))).resolve()
        avatar_id = str(record.get("musetalk_avatar_id", ""))
        avatar_manifest = (avatar_root / avatar_id / "manifest.json").resolve()
        current_manifest_sha = _sha256(avatar_manifest) if avatar_manifest.is_file() else ""
        if (
            not idle.is_file()
            or _sha256(idle) != record.get("idle_sha256")
            or avatar_root not in avatar_manifest.parents
            or not avatar_manifest.is_file()
        ):
            raise ValueError(f"combination.candidate_hash_mismatch:{slug}")
        avatar_payload = json.loads(avatar_manifest.read_text(encoding="utf-8"))
        if (
            avatar_payload.get("avatar_id") != avatar_id
            or avatar_payload.get("presentation") != "complete_scene"
            or avatar_payload.get("engine") != "musetalk15"
            or avatar_payload.get("visual_approved") not in {False, True}
        ):
            raise ValueError(f"combination.candidate_avatar_invalid:{slug}")
        if avatar_payload.get("visual_approved") is False:
            if current_manifest_sha != record.get("musetalk_manifest_sha256"):
                raise ValueError(f"combination.candidate_hash_mismatch:{slug}")
            approved_payload = {**avatar_payload, "visual_approved": True}
            pending_approvals.append((avatar_manifest, approved_payload))
            approved_sha = hashlib.sha256(
                (json.dumps(approved_payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            ).hexdigest()
        else:
            existing_v2 = binding_root / "scene-bindings.v2.json"
            existing_payload = json.loads(existing_v2.read_text(encoding="utf-8")) if existing_v2.is_file() else {}
            existing = next((item for item in existing_payload.get("bindings", []) if (
                item.get("appearance_id") == blue_id
                and item.get("scene_id") == record["scene_id"]
                and item.get("speaking_avatar_id") == avatar_id
            )), None)
            if existing is None or existing.get("talking_sha256") != current_manifest_sha:
                raise ValueError(f"combination.approval_provenance_missing:{slug}")
            approved_sha = current_manifest_sha
        idle_target = binding_root / "assets" / blue_id / f"{record['scene_id']}-idle.mp4"
        _atomic_copy(idle, idle_target)
        idle_id = _rendition_id(blue_id, record["scene_id"], "idle", record["idle_sha256"])
        talking_id = _rendition_id(blue_id, record["scene_id"], "talking", approved_sha)
        bindings.append({
            "appearance_id": blue_id,
            "appearance_label": str(candidate.get("appearance_label", "蓝白碎花上衣")),
            "scene_id": record["scene_id"],
            "slug": slug,
            "idle_relative_path": idle_target.relative_to(binding_root).as_posix(),
            "idle_sha256": record["idle_sha256"],
            "speaking_avatar_id": avatar_id,
            "talking_sha256": approved_sha,
            "idle_rendition_id": idle_id,
            "talking_rendition_id": talking_id,
            "engine": "musetalk",
        })
        renditions.extend((
            {"rendition_id": idle_id, "kind": "idle", "source_ids": source_ids, "scene_id": record["scene_id"], "status": "active" if active_appearance_id == blue_id and manifest.payload.get("active_scene_id") == record["scene_id"] else "approved", "sha256": record["idle_sha256"]},
            {"rendition_id": talking_id, "kind": "talking", "source_ids": source_ids, "scene_id": record["scene_id"], "status": "active" if active_appearance_id == blue_id and manifest.payload.get("active_scene_id") == record["scene_id"] else "approved", "sha256": approved_sha},
        ))

    if len({(item["appearance_id"], item["scene_id"]) for item in bindings}) != len(bindings):
        raise ValueError("scene.binding_duplicate")
    for path, payload in pending_approvals:
        _atomic_json(path, payload)
    v2_payload = {
        "schema_version": 2,
        "source_pack_id": manifest.payload["pack_id"],
        "bindings": sorted(bindings, key=lambda item: (item["appearance_id"], item["scene_id"])),
    }
    v2_path = binding_root / "scene-bindings.v2.json"
    _atomic_json(v2_path, v2_payload)
    committed = source_pack.register_combinations(
        appearances=[
            {"appearance_id": red_id, "source_ids": source_ids, "confirmed": True},
            {"appearance_id": blue_id, "source_ids": source_ids, "confirmed": True},
        ],
        renditions=renditions,
        active_appearance_id=active_appearance_id,
    )
    return {
        "schema_version": 1,
        "result": "PASS",
        "revision": committed.revision,
        "active_appearance_id": committed.payload["active_appearance_id"],
        "active_scene_id": committed.payload["active_scene_id"],
        "appearance_count": 2,
        "combination_count": len(bindings),
        "common_scene_count": len(candidate["records"]),
        "binding_manifest": str(v2_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    print(json.dumps(install(
        data_root=parser.parse_args().data_root,
        candidate_manifest_path=parser.parse_args().candidate_manifest,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
