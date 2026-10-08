"""Read-only X3.1 scene catalog backed by real public background assets."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

from cyberwife.application.source_pack_service import SourcePackService


_SCENE_NAMESPACE = UUID("ed3d7f23-a0b9-4f42-a8b7-65ec13ff70cd")


@dataclass(frozen=True)
class SceneDefinition:
    slug: str
    label: str
    description: str
    filename: str
    focus: tuple[float, float]
    safe_area: tuple[float, float, float, float]


DEFAULT_SCENES = (
    SceneDefinition("blue-hour-living", "蓝调客厅", "暖灯与城市蓝调", "blue-hour-living.webp", (0.50, 0.42), (0.08, 0.08, 0.92, 0.92)),
    SceneDefinition("morning-bedroom", "清晨卧室", "柔和晨光与浅木色", "morning-bedroom.webp", (0.50, 0.42), (0.08, 0.08, 0.92, 0.92)),
    SceneDefinition("rainy-library", "雨夜书房", "安静深色与雨窗", "rainy-library.webp", (0.50, 0.42), (0.08, 0.08, 0.92, 0.92)),
    SceneDefinition("garden-sunroom", "花园阳光房", "自然绿意与午后光", "garden-sunroom.webp", (0.50, 0.42), (0.08, 0.08, 0.92, 0.92)),
)


class ScenePresetService:
    def __init__(
        self,
        source_pack: SourcePackService,
        backgrounds_root: Path,
        *,
        definitions: tuple[SceneDefinition, ...] = DEFAULT_SCENES,
        binding_root: Path | None = None,
        avatar_root: Path | None = None,
    ) -> None:
        self._source_pack = source_pack
        self._root = Path(backgrounds_root).resolve()
        self._definitions = definitions
        self._binding_root = Path(binding_root).resolve() if binding_root else None
        self._avatar_root = Path(avatar_root).resolve() if avatar_root else None

    @staticmethod
    def scene_id(slug: str) -> str:
        return str(uuid5(_SCENE_NAMESPACE, f"cyberwife-scene:{slug}"))

    def _asset(self, definition: SceneDefinition) -> tuple[Path, str]:
        target = (self._root / definition.filename).resolve()
        if self._root not in target.parents or target.suffix.lower() != ".webp":
            raise ValueError("scene.invalid_asset_path")
        if not target.is_file():
            raise FileNotFoundError(f"scene.asset_missing:{definition.slug}")
        return target, hashlib.sha256(target.read_bytes()).hexdigest()

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _bindings(self) -> dict[str, dict]:
        if self._binding_root is None:
            return {}
        target = self._binding_root / "scene-bindings.v1.json"
        if not target.is_file():
            return {}
        payload = json.loads(target.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("bindings"), list):
            raise ValueError("scene.binding_manifest_invalid")
        result: dict[str, dict] = {}
        for item in payload["bindings"]:
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", str(item.get("speaking_avatar_id", ""))):
                raise ValueError("scene.binding_manifest_invalid")
            scene_id = str(item.get("scene_id", ""))
            if scene_id in result:
                raise ValueError("scene.binding_duplicate")
            result[scene_id] = dict(item)
        return result

    def _approved_binding(self, scene_id: str, manifest, bindings: dict[str, dict]) -> dict | None:
        item = bindings.get(scene_id)
        if item is None or self._binding_root is None or self._avatar_root is None:
            return None
        idle_path = (self._binding_root / str(item.get("idle_relative_path", ""))).resolve()
        avatar_path = (self._avatar_root / str(item.get("speaking_avatar_id", ""))).resolve()
        avatar_manifest = avatar_path / "manifest.json"
        if (
            self._binding_root not in idle_path.parents
            or self._avatar_root not in avatar_path.parents
            or not idle_path.is_file()
            or not avatar_manifest.is_file()
        ):
            return None
        idle_sha = self._sha256(idle_path)
        talking_sha = self._sha256(avatar_manifest)
        if idle_sha != item.get("idle_sha256") or talking_sha != item.get("talking_sha256"):
            return None
        avatar_payload = json.loads(avatar_manifest.read_text(encoding="utf-8"))
        if (
            avatar_payload.get("avatar_id") != item.get("speaking_avatar_id")
            or avatar_payload.get("presentation") != "complete_scene"
            or avatar_payload.get("visual_approved") is not True
        ):
            return None
        approved = {
            record["kind"]: record for record in manifest.payload["renditions"]
            if record["scene_id"] == scene_id and record["status"] in {"approved", "active"}
        }
        if (
            approved.get("idle", {}).get("sha256") != idle_sha
            or approved.get("talking", {}).get("sha256") != talking_sha
        ):
            return None
        return {**item, "idle_path": idle_path, "avatar_manifest": avatar_payload}

    def ensure_registered(self) -> dict:
        catalog: list[dict] = []
        manifest_scenes: list[dict] = []
        for definition in self._definitions:
            _, sha256 = self._asset(definition)
            scene_id = self.scene_id(definition.slug)
            manifest_scenes.append({
                "scene_id": scene_id,
                "label": definition.label,
                "asset_sha256": sha256,
            })
            catalog.append({
                "scene_id": scene_id,
                "slug": definition.slug,
                "label": definition.label,
                "description": definition.description,
                "asset_sha256": sha256,
                "preview_url": f"/backgrounds/{definition.filename}",
                "focus": {"x": definition.focus[0], "y": definition.focus[1]},
                "safe_area": {
                    "left": definition.safe_area[0], "top": definition.safe_area[1],
                    "right": definition.safe_area[2], "bottom": definition.safe_area[3],
                },
                "quality_status": "preview_only",
                "can_activate": False,
            })
        manifest = self._source_pack.register_scenes(manifest_scenes)
        bindings = self._bindings()
        active_scene_id = manifest.payload.get("active_scene_id")
        for item in catalog:
            binding = self._approved_binding(item["scene_id"], manifest, bindings)
            active = binding is not None and active_scene_id == item["scene_id"]
            item["quality_status"] = "active" if active else "approved" if binding else "preview_only"
            item["can_activate"] = binding is not None
            item["idle_url"] = (
                f"/api/v1/scene-presets/{item['scene_id']}/idle" if binding else None
            )
            item["speaking_avatar_id"] = binding.get("speaking_avatar_id") if binding else None
        return {
            "schema_version": 1,
            "revision": manifest.revision,
            "active_scene_id": active_scene_id,
            "items": catalog,
        }

    def activate(self, scene_id: str, *, expected_revision: int) -> dict:
        catalog = self.ensure_registered()
        target = next((item for item in catalog["items"] if item["scene_id"] == scene_id), None)
        if target is None:
            raise ValueError("scene.not_found")
        if not target["can_activate"]:
            raise ValueError("scene.renditions_incomplete")
        self._source_pack.activate_scene(scene_id, expected_revision=expected_revision)
        return self.ensure_registered()

    def idle_path(self, scene_id: str) -> Path:
        manifest = self._source_pack.load()
        if manifest is None:
            raise ValueError("source_pack.required")
        binding = self._approved_binding(scene_id, manifest, self._bindings())
        if binding is None:
            raise FileNotFoundError("scene.renditions_incomplete")
        return binding["idle_path"]

    def active_avatar(self) -> dict | None:
        manifest = self._source_pack.load()
        if manifest is None or manifest.payload.get("active_scene_id") is None:
            return None
        scene_id = manifest.payload["active_scene_id"]
        binding = self._approved_binding(scene_id, manifest, self._bindings())
        if binding is None:
            return None
        avatar = binding["avatar_manifest"]
        return {
            "status": "active",
            "engine": "wav2lip",
            "avatar_id": binding["speaking_avatar_id"],
            "source_sha256": avatar.get("source_sha256"),
            "frame_count": int(avatar.get("frame_count", 0)),
            "frame_size": avatar.get("frame_size"),
            "face_box": avatar.get("coordinates"),
            "scene_id": scene_id,
            "idle_url": f"/api/v1/scene-presets/{scene_id}/idle",
            "single_surface_ready": True,
        }
