"""Read-only X3.1 scene catalog backed by real public background assets."""
from __future__ import annotations

import hashlib
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
    ) -> None:
        self._source_pack = source_pack
        self._root = Path(backgrounds_root).resolve()
        self._definitions = definitions

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
        return {
            "schema_version": 1,
            "revision": manifest.revision,
            "active_scene_id": manifest.payload.get("active_scene_id"),
            "items": catalog,
        }

