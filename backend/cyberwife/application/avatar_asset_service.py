"""Content-addressed portrait → LiveTalking Avatar build orchestration."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from cyberwife.ports.assets import AssetStorePort


_SAFE_AVATAR_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class AvatarAssetService:
    """Build private Avatar data without exposing filesystem paths in the API."""

    def __init__(
        self,
        repository,
        *,
        asset_store: AssetStorePort,
        avatar_root: Path,
        idle_job_root: Path | None = None,
        idle_pipeline_runner=None,
    ) -> None:
        self._repository = repository
        self._store = asset_store
        self._avatar_root = Path(avatar_root)
        self._idle_job_root = Path(idle_job_root or self._avatar_root.parent / "idle-jobs")
        self._idle_pipeline_runner = idle_pipeline_runner
        self._idle_job_lock = threading.RLock()
        self._running_idle_jobs: set[int] = set()

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
        preserve_scene: bool = False,
    ) -> dict:
        """Build and stage a generated idle loop; never bypass visual approval."""
        if not visually_approved:
            raise ValueError("avatar.visual_approval_required")
        row = self._repository.get_avatar_derivative(derivative_id)
        if row is None:
            raise KeyError(derivative_id)
        source = self._store.resolve(str(row["relative_path"]))
        video_sha = hashlib.sha256(Path(idle_video).read_bytes()).hexdigest()
        from ops.build_video_avatar import (
            AVATAR_BUILD_REVISION,
            SCENE_AVATAR_BUILD_REVISION,
            build,
        )

        build_revision = (
            SCENE_AVATAR_BUILD_REVISION if preserve_scene else AVATAR_BUILD_REVISION
        )

        avatar_id = (
            f"wav2lip256_idle_p_{str(row['source_sha256'])[:16]}_"
            f"{video_sha[:8]}_{build_revision}"
        )

        target = self._avatar_root / avatar_id
        if target.is_dir() and (target / "manifest.json").is_file():
            existing = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            if (
                existing.get("source_sha256") != row["source_sha256"]
                or existing.get("idle_video_sha256") != video_sha
            ):
                raise RuntimeError("avatar.existing_artifact_mismatch")
        else:
            target = build(
                source,
                Path(idle_video),
                self._avatar_root,
                avatar_id,
                preserve_frame=preserve_scene,
            )
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

    def _job_dir(self, derivative_id: int) -> Path:
        return self._idle_job_root / str(int(derivative_id))

    def _job_path(self, derivative_id: int) -> Path:
        return self._job_dir(derivative_id) / "job.json"

    def _write_job(self, derivative_id: int, payload: dict) -> dict:
        job_dir = self._job_dir(derivative_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            **payload,
            "derivative_id": int(derivative_id),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        target = self._job_path(derivative_id)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
        return payload

    def _read_job(self, derivative_id: int) -> dict | None:
        target = self._job_path(derivative_id)
        if not target.is_file():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    @staticmethod
    def public_idle_job(payload: dict) -> dict:
        return {
            key: payload.get(key)
            for key in (
                "derivative_id", "status", "phase", "progress", "error_code",
                "has_frontal_preview", "has_video_preview", "has_scene_previews",
                "has_sequence_previews", "has_intro_preview", "has_outro_preview",
                "sequence_version", "speaking_avatar_id", "single_surface_ready",
                "scene_ids", "updated_at",
            )
        }

    def queue_idle_generation(self, derivative_id: int) -> dict:
        with self._idle_job_lock:
            row = self._repository.get_avatar_derivative(derivative_id)
            if row is None:
                raise KeyError(derivative_id)
            if row["status"] not in {"ready", "active"}:
                raise ValueError("avatar.static_build_required")
            existing = self._read_job(derivative_id)
            if existing and existing.get("status") in {"queued", "generating"}:
                return self.public_idle_job(existing)
            if existing and existing.get("status") in {"awaiting_approval", "active"}:
                return self.public_idle_job(existing)
            paths = (
                self._idle_job_root.glob("*/job.json")
                if self._idle_job_root.exists()
                else ()
            )
            for path in paths:
                other = json.loads(path.read_text(encoding="utf-8"))
                if other.get("status") in {"queued", "generating"}:
                    raise RuntimeError("avatar.generation_busy")
            payload = self._write_job(derivative_id, {
                "status": "queued", "phase": "waiting_for_gpu", "progress": 0,
                "error_code": None, "has_frontal_preview": False,
                "has_video_preview": False,
            })
            return self.public_idle_job(payload)

    def run_idle_generation(self, derivative_id: int) -> None:
        with self._idle_job_lock:
            current = self._read_job(derivative_id)
            if (
                derivative_id in self._running_idle_jobs
                or current is None
                or current.get("status") not in {"queued", "generating"}
            ):
                return
            self._running_idle_jobs.add(derivative_id)
            self._write_job(derivative_id, {**current, "status": "generating"})
        try:
            row = self._repository.get_avatar_derivative(derivative_id)
            if row is None:
                raise KeyError(derivative_id)
            source = self._store.resolve(str(row["relative_path"]))

            def progress(phase: str, value: int) -> None:
                with self._idle_job_lock:
                    state = self._read_job(derivative_id) or {}
                    self._write_job(derivative_id, {
                        **state, "status": "generating", "phase": phase,
                        "progress": max(0, min(99, int(value))),
                    })

            runner = self._idle_pipeline_runner
            if runner is None:
                from ops.avatar_idle_pipeline import run_pipeline
                runner = run_pipeline
            result = runner(source, self._job_dir(derivative_id), progress)
            frontal = Path(result["frontal_path"]).resolve()
            video = Path(result["video_path"]).resolve()
            scene_manifest = Path(result["scene_manifest_path"]).resolve()
            job_dir = self._job_dir(derivative_id).resolve()
            if (
                job_dir not in frontal.parents or job_dir not in video.parents
                or job_dir not in scene_manifest.parents
            ):
                raise RuntimeError("avatar.pipeline_output_outside_job")
            if not frontal.is_file() or not video.is_file() or not scene_manifest.is_file():
                raise RuntimeError("avatar.pipeline_output_missing")
            scene_payload = json.loads(scene_manifest.read_text(encoding="utf-8"))
            scene_ids = sorted(scene_payload.get("outputs", {}))
            if len(scene_ids) < 4:
                raise RuntimeError("avatar.scene_composites_incomplete")
            with self._idle_job_lock:
                state = self._read_job(derivative_id) or {}
                self._write_job(derivative_id, {
                    **state,
                    "status": "awaiting_approval",
                    "phase": "visual_review",
                    "progress": 100,
                    "frontal_path": str(frontal),
                    "video_path": str(video),
                    "scene_manifest_path": str(scene_manifest),
                    "has_frontal_preview": True,
                    "has_video_preview": True,
                    "has_scene_previews": True,
                    "scene_ids": scene_ids,
                })
        except Exception as exc:
            with self._idle_job_lock:
                state = self._read_job(derivative_id) or {}
                self._write_job(derivative_id, {
                    **state,
                    "status": "failed",
                    "phase": "failed",
                    "error_code": (str(exc).splitlines()[0] or exc.__class__.__name__)[:160],
                })
        finally:
            with self._idle_job_lock:
                self._running_idle_jobs.discard(derivative_id)

    def get_idle_generation(self, derivative_id: int) -> dict:
        payload = self._read_job(derivative_id)
        if payload is None:
            raise KeyError(derivative_id)
        return self.public_idle_job(payload)

    def idle_preview_path(self, derivative_id: int, kind: str) -> Path:
        path_keys = {
            "frontal": "frontal_path",
            "video": "video_path",
            "intro": "intro_path",
            "outro": "outro_path",
        }
        if kind not in path_keys:
            raise ValueError("avatar.invalid_preview_kind")
        payload = self._read_job(derivative_id)
        if payload is None or payload.get("status") not in {"awaiting_approval", "active"}:
            raise KeyError(derivative_id)
        raw_path = payload.get(path_keys[kind])
        if not raw_path:
            raise KeyError(kind)
        target = Path(raw_path).resolve()
        if self._job_dir(derivative_id).resolve() not in target.parents or not target.is_file():
            raise ValueError("avatar.invalid_preview_path")
        return target

    def install_approved_sequence(
        self,
        derivative_id: int,
        *,
        manifest_path: Path,
        close_keyframe: Path,
        visually_approved: bool,
    ) -> dict:
        """Install an approved sequence and bind its idle scene to speaking output."""
        if not visually_approved:
            raise ValueError("avatar.visual_approval_required")
        row = self._repository.get_avatar_derivative(derivative_id)
        if row is None:
            raise KeyError(derivative_id)
        if row.get("status") != "active":
            raise ValueError("avatar.active_build_required")
        payload = self._read_job(derivative_id)
        if payload is None or payload.get("status") != "active":
            raise ValueError("avatar.active_idle_required")

        manifest_path = Path(manifest_path).resolve()
        close_keyframe = Path(close_keyframe).resolve()
        if not manifest_path.is_file() or not close_keyframe.is_file():
            raise FileNotFoundError("avatar.sequence_input_missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("generation_mode") != "direct_complete_scene_sequence":
            raise ValueError("avatar.invalid_sequence_manifest")
        if manifest.get("matting") is not False:
            raise ValueError("avatar.sequence_matting_not_allowed")
        expected_close = str(manifest.get("close_keyframe", {}).get("sha256", ""))
        if hashlib.sha256(close_keyframe.read_bytes()).hexdigest() != expected_close:
            raise ValueError("avatar.sequence_keyframe_mismatch")

        sources: dict[str, Path] = {}
        for kind in ("intro", "idle", "outro"):
            record = manifest.get(kind)
            if not isinstance(record, dict):
                raise ValueError("avatar.invalid_sequence_manifest")
            source = Path(str(record.get("path", ""))).resolve()
            if source.parent != manifest_path.parent or not source.is_file():
                raise ValueError("avatar.sequence_output_outside_manifest")
            if hashlib.sha256(source.read_bytes()).hexdigest() != record.get("sha256"):
                raise ValueError("avatar.sequence_output_mismatch")
            sources[kind] = source

        job_dir = self._job_dir(derivative_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        revision = expected_close[:12]
        destinations = {
            "intro": job_dir / f"sequence-{revision}-intro.mp4",
            "idle": job_dir / f"sequence-{revision}-idle.mp4",
            "outro": job_dir / f"sequence-{revision}-outro.mp4",
            "frontal": job_dir / f"sequence-{revision}-frontal.png",
            "manifest": job_dir / f"sequence-{revision}-manifest.json",
        }
        copy_sources = {
            "intro": sources["intro"], "idle": sources["idle"],
            "outro": sources["outro"], "frontal": close_keyframe,
            "manifest": manifest_path,
        }
        for key, source in copy_sources.items():
            temporary = destinations[key].with_suffix(destinations[key].suffix + ".tmp")
            shutil.copy2(source, temporary)
            temporary.replace(destinations[key])

        speaking = self.promote_idle_video(
            derivative_id,
            destinations["idle"],
            visually_approved=True,
            preserve_scene=True,
        )
        updated = self._write_job(derivative_id, {
            **payload,
            "frontal_path": str(destinations["frontal"].resolve()),
            "video_path": str(destinations["idle"].resolve()),
            "intro_path": str(destinations["intro"].resolve()),
            "outro_path": str(destinations["outro"].resolve()),
            "sequence_manifest_path": str(destinations["manifest"].resolve()),
            "has_frontal_preview": True,
            "has_video_preview": True,
            "has_sequence_previews": True,
            "has_intro_preview": True,
            "has_outro_preview": True,
            "sequence_version": f"ux13-frontal-{revision}",
            "speaking_avatar_id": speaking["avatar_id"],
            "single_surface_ready": True,
            "phase": "complete",
            "progress": 100,
        })
        return self.public_idle_job(updated)

    def idle_scene_preview_path(self, derivative_id: int, scene_id: str) -> Path:
        if not re.fullmatch(r"[a-z0-9-]{1,64}", scene_id):
            raise ValueError("avatar.invalid_scene_id")
        payload = self._read_job(derivative_id)
        if payload is None or payload.get("status") not in {"awaiting_approval", "active"}:
            raise KeyError(derivative_id)
        manifest_path = Path(payload.get("scene_manifest_path", "")).resolve()
        job_dir = self._job_dir(derivative_id).resolve()
        if job_dir not in manifest_path.parents or not manifest_path.is_file():
            raise ValueError("avatar.invalid_scene_manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        record = manifest.get("outputs", {}).get(scene_id)
        if not isinstance(record, dict):
            raise KeyError(scene_id)
        target = Path(str(record.get("path", ""))).resolve()
        if job_dir not in target.parents or not target.is_file():
            raise ValueError("avatar.invalid_scene_preview_path")
        return target

    def approve_idle_generation(self, derivative_id: int) -> dict:
        with self._idle_job_lock:
            payload = self._read_job(derivative_id)
            if payload is None or payload.get("status") != "awaiting_approval":
                raise ValueError("avatar.visual_approval_required")
            row = self.promote_idle_video(
                derivative_id, Path(payload["video_path"]), visually_approved=True
            )
            if row.get("status") != "active":
                row = self._repository.activate_avatar_derivative(derivative_id)
            self._write_job(derivative_id, {
                **payload, "status": "active", "phase": "complete", "progress": 100,
            })
            return row

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
