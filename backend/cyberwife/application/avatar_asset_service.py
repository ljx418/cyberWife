"""Content-addressed portrait → LiveTalking Avatar build orchestration."""
from __future__ import annotations

import hashlib
import json
import re
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
    ) -> dict:
        """Build and stage a generated idle loop; never bypass visual approval."""
        if not visually_approved:
            raise ValueError("avatar.visual_approval_required")
        row = self._repository.get_avatar_derivative(derivative_id)
        if row is None:
            raise KeyError(derivative_id)
        source = self._store.resolve(str(row["relative_path"]))
        video_sha = hashlib.sha256(Path(idle_video).read_bytes()).hexdigest()
        from ops.build_video_avatar import AVATAR_BUILD_REVISION, build

        avatar_id = (
            f"wav2lip256_idle_p_{str(row['source_sha256'])[:16]}_"
            f"{video_sha[:8]}_{AVATAR_BUILD_REVISION}"
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
                "has_frontal_preview", "has_video_preview", "updated_at",
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
            job_dir = self._job_dir(derivative_id).resolve()
            if job_dir not in frontal.parents or job_dir not in video.parents:
                raise RuntimeError("avatar.pipeline_output_outside_job")
            if not frontal.is_file() or not video.is_file():
                raise RuntimeError("avatar.pipeline_output_missing")
            with self._idle_job_lock:
                state = self._read_job(derivative_id) or {}
                self._write_job(derivative_id, {
                    **state,
                    "status": "awaiting_approval",
                    "phase": "visual_review",
                    "progress": 100,
                    "frontal_path": str(frontal),
                    "video_path": str(video),
                    "has_frontal_preview": True,
                    "has_video_preview": True,
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
        if kind not in {"frontal", "video"}:
            raise ValueError("avatar.invalid_preview_kind")
        payload = self._read_job(derivative_id)
        if payload is None or payload.get("status") not in {"awaiting_approval", "active"}:
            raise KeyError(derivative_id)
        target = Path(payload[f"{kind}_path"]).resolve()
        if self._job_dir(derivative_id).resolve() not in target.parents or not target.is_file():
            raise ValueError("avatar.invalid_preview_path")
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
