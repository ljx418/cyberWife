"""ApiGateway — REST + WebSocket composition root。

M1 阶段：仅暴露 §6 REST 表（健康/草稿/consent/profile）+ 一个简单的 GET /health。
完整的 17 个 REST + 8 个 WS 在 M2 起逐步接入。
"""
from __future__ import annotations

import asyncio
import json
import struct
import threading
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile, status, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.session_runtime import SessionRuntime
from cyberwife.domain.conversation import RecordingPolicy, SessionState
from cyberwife.ports.assets import AssetStorePort
from cyberwife.ports.repositories import ApplicationRepositoryPort


def _gen_trace_id() -> str:
    """ULID 26 字符 Crockford base32（§4）。"""
    import secrets

    # Crockford base32 字母表（不含 I/L/O/U）
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    # 16 字节随机数 = 32 hex 字符 → 取 mod 32 → 32 个 5-bit 值 → 32 个 Crockford 字符
    raw = secrets.token_bytes(32)
    return "".join(alphabet[b % 32] for b in raw)[:26]


# implementation-contracts §16 错误码目录
_ERRORS = {
    "auth.consent_required": (403, "open_onboarding", False),
    "consent.revoked": (409, "open_onboarding", False),
    "asset.invalid": (422, "open_settings", False),
    "asset.too_large": (413, "open_settings", False),
    "asset.version_conflict": (409, "retry", True),
    "session.not_found": (404, "none", False),
    "session.recording_policy_invalid": (422, "none", False),
    "memory.not_found": (404, "none", False),
    "memory.confirm_required": (412, "confirm_dialog", False),
    "audit.entity_not_found": (404, "none", False),
    "retention.invalid_clock": (422, "none", False),
    "health.component_unavailable": (503, "retry_later", True),
    "health.degraded": (200, "open_status", False),
    "frame.size_limit": (413, "none", False),
    "turn.cancelled": (200, "none", False),
    "turn.late_event": (200, "none", False),
    "interrupted": (200, "none", False),
    "internal.error": (500, "retry_later", True),
}


def error_envelope(code: str, message: str, *, trace_id: str | None = None) -> dict:
    """构造符合 schemas/errors/error_envelope.schema.json 的错误信封。"""
    http_status, user_action, retryable = _ERRORS.get(code, _ERRORS["internal.error"])
    return {
        "code": code,
        "message": message,
        "user_action": user_action,
        "trace_id": trace_id or _gen_trace_id(),
        "retryable": retryable,
    }


class ApiGateway:
    """Application-facing HTTP/WS gateway; concrete wiring lives in api.server."""

    def __init__(
        self,
        registry: ModelRegistry,
        aggregator: HealthAggregator,
        repository: ApplicationRepositoryPort | None = None,
        assets_root: Path | None = None,
        asset_store: AssetStorePort | None = None,
        orchestrator: ConversationOrchestrator | None = None,
        turn_pipeline=None,
        memory_service=None,
        retention_service=None,
        launcher_service=None,
        tts_probe=None,
        tts_preview=None,
        shutdown_hooks=None,
        static_root: Path | None = None,
        avatar_asset_service=None,
        privacy_cache_clear=None,
    ) -> None:
        self._registry = registry
        self._aggregator = aggregator
        self._repository = repository
        self._orchestrator = orchestrator or ConversationOrchestrator()
        self._turn_pipeline = turn_pipeline
        self._memory_service = memory_service
        self._retention_service = retention_service
        self._launcher_service = launcher_service
        self._tts_probe = tts_probe
        self._tts_preview = tts_preview
        self._shutdown_hooks = tuple(shutdown_hooks or ())
        self._avatar_asset_service = avatar_asset_service
        self._privacy_cache_clear = privacy_cache_clear
        self._asset_store = asset_store
        self._static_root = Path(static_root) if static_root else Path(__file__).resolve().parents[3] / "prototype" / "dist"
        self._session_runtimes: dict[int, SessionRuntime] = {}
        self._session_tokens: dict[str, int] = {}
        self._session_token_by_id: dict[int, str] = {}
        # ADR-006 修订：默认 C:\workSpace\cyberWife\assets\；可通过 ctor 覆盖
        self._assets_root = Path(assets_root) if assets_root else Path(
            "/mnt/c/workSpace/cyberWife/assets"
        )

    @asynccontextmanager
    async def lifespan(self, app: FastAPI) -> AsyncIterator[None]:
        """Run startup compensation and the daily local 03:00 retention scan."""
        task = None
        health_task = None
        if self._retention_service is not None:
            await asyncio.to_thread(self._retention_service.scan_with_retry)

            async def scheduled_retention() -> None:
                while True:
                    delay = max(
                        1.0,
                        (self._retention_service.next_scan_at() - datetime.now().astimezone()).total_seconds(),
                    )
                    await asyncio.sleep(delay)
                    await asyncio.to_thread(self._retention_service.scan_with_retry)

            task = asyncio.create_task(scheduled_retention(), name="retention-03-local")

        async def startup_health_probe() -> None:
            # The TTS functional probe calls this running Gateway's internal
            # endpoint, so probing must begin after ASGI startup rather than
            # in the composition root. Failures stay visible through health;
            # they do not remove the recovery control plane.
            await asyncio.sleep(0.2)
            for component in self._registry.all_components():
                try:
                    await asyncio.to_thread(self._aggregator.probe_component, component)
                except (KeyError, RuntimeError):
                    continue

        if self._aggregator.supports_functional_probes:
            health_task = asyncio.create_task(startup_health_probe(), name="startup-functional-probes")
        try:
            yield
        finally:
            if health_task is not None:
                health_task.cancel()
                await asyncio.gather(health_task, return_exceptions=True)
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            for hook in self._shutdown_hooks:
                await asyncio.to_thread(hook)

    def build_app(self) -> FastAPI:
        app = FastAPI(title="cyberWife V1 API Gateway", version="1.0.0", lifespan=self.lifespan)

        def resolve_session_ref(session_ref: str) -> int | None:
            mapped = self._session_tokens.get(session_ref)
            if mapped is not None:
                return mapped
            if not session_ref.isdecimal():
                return None
            session_id = int(session_ref)
            session = self._orchestrator.get(session_id)
            if session is None or session.recording_policy == RecordingPolicy.NONE:
                return None
            return session_id

        def public_ref(session_id: int) -> str:
            return self._session_token_by_id.get(session_id, str(session_id))

        def register_private_ref(session_id: int) -> str:
            previous = self._session_token_by_id.pop(session_id, None)
            if previous:
                self._session_tokens.pop(previous, None)
            token = uuid.uuid4().hex
            self._session_tokens[token] = session_id
            self._session_token_by_id[session_id] = token
            return token

        def forget_private_ref(session_id: int) -> None:
            token = self._session_token_by_id.pop(session_id, None)
            if token:
                self._session_tokens.pop(token, None)

        # ── CORS（loopback 内部 M2-stretch 上传/录音；NFR-18 仅 loopback）──────────
        # 限制 origin 为 Vite dev server 与可能的 Win 浏览器 loopback；
        # 不允许任意 origin（PRD §3 隐私边界 + ADR-005）
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[
                "http://127.0.0.1:4173",
                "http://localhost:4173",
                "http://127.0.0.1:7860",
            ],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
            allow_headers=["*"],
        )

        @app.exception_handler(HTTPException)
        async def _http_exc_handler(request: Request, exc: HTTPException) -> JSONResponse:
            """HTTPException → 统一错误信封。"""
            code = "internal.error"
            # 路由可在标准 code 后追加不含隐私的本地诊断；错误类型仍必须
            # 保持为已登记 code，不能因为 ``asset.invalid: ...`` 退化成
            # ``internal.error``，否则前端会给出错误的恢复动作。
            if isinstance(exc.detail, str):
                candidate = exc.detail.split(":", 1)[0].strip()
                if candidate in _ERRORS:
                    code = candidate
            payload = error_envelope(code, str(exc.detail) if exc.detail else code)
            return JSONResponse(status_code=exc.status_code, content=payload)

        # ── 路由 ────────────────────────────────────────────────────
        @app.get("/api/v1/health")
        async def health() -> dict:
            return self._aggregator.snapshot()

        @app.post("/api/v1/internal/probe/tts")
        async def probe_loaded_tts() -> dict:
            if self._tts_probe is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            return await asyncio.to_thread(self._tts_probe)

        @app.post("/api/v1/tts/preview")
        async def preview_tts(payload: dict) -> Response:
            if self._tts_preview is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            text = str(payload.get("text", "")).strip()
            if not text or len(text) > 120:
                raise HTTPException(status_code=422, detail="asset.invalid")
            wav = await asyncio.to_thread(self._tts_preview, text)
            return Response(
                content=wav,
                media_type="audio/wav",
                headers={"Cache-Control": "no-store, private"},
            )

        @app.get("/api/v1/runtime/metrics")
        async def runtime_metrics() -> dict:
            if self._turn_pipeline is None:
                return {"active_turns": 0, "llm_queue_depth": 0, "llm_queue_capacity": 0}
            result = self._turn_pipeline.metrics()
            snapshots = {
                self._orchestrator.public_session_id(session_id): {
                    "active_turns": snapshot.active_turns,
                    "outbound_depth": snapshot.outbound_depth,
                    "outbound_capacity": snapshot.outbound_capacity,
                    "late_events_dropped": snapshot.late_events_dropped,
                }
                for session_id, runtime in tuple(self._session_runtimes.items())
                for snapshot in (runtime.snapshot(),)
            }
            result["session_runtimes"] = snapshots
            result["runtime_tasks"] = sum(item["active_turns"] for item in snapshots.values())
            result["outbound_queue_depth"] = sum(item["outbound_depth"] for item in snapshots.values())
            # Names/counts only: no stack, request, text, audio or filesystem
            # data.  This distinguishes leaked Python workers from native
            # Torch/ONNX pools during the local endurance gate.
            thread_names = Counter(thread.name for thread in threading.enumerate())
            result["python_thread_count"] = sum(thread_names.values())
            result["python_threads_by_name"] = dict(sorted(thread_names.items()))
            return result

        @app.get("/api/v1/retention/now")
        async def retention_now() -> dict:
            if self._retention_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                now = self._retention_service.now()
            except ValueError:
                raise HTTPException(status_code=422, detail="retention.invalid_clock")
            return {"now": now.isoformat(), "next_scan_at": self._retention_service.next_scan_at(now).isoformat(), "disk": self._retention_service.disk_status()}

        @app.post("/api/v1/retention/run")
        async def retention_run() -> dict:
            if self._retention_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                return await asyncio.to_thread(self._retention_service.scan_with_retry)
            except ValueError:
                raise HTTPException(status_code=422, detail="retention.invalid_clock")

        @app.post("/api/v1/health/{component}/retry")
        async def retry_component(component: str) -> dict:
            import asyncio
            try:
                result = await asyncio.to_thread(self._aggregator.probe_component, component)
            except KeyError:
                raise HTTPException(status_code=404, detail="health.component_unavailable")
            if result["status"] != "ready" and self._launcher_service is not None:
                if component == "tts" and hasattr(self._launcher_service, "schedule_recover"):
                    recovery = self._launcher_service.schedule_recover("tts")
                    return JSONResponse(status_code=202, content={**result, "recovery": recovery})
                try:
                    recovery = await asyncio.to_thread(self._launcher_service.recover, component)
                    result = await asyncio.to_thread(self._aggregator.probe_component, component)
                    result["recovery"] = recovery
                except (ValueError, RuntimeError):
                    pass
            if result["status"] != "ready":
                return JSONResponse(status_code=503, content=error_envelope(
                    "health.component_unavailable", result.get("last_error", "probe_failed")
                ))
            return result

        @app.post("/api/v1/launcher/recover")
        async def recover_launcher(payload: dict | None = None) -> dict:
            if self._launcher_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            component = str((payload or {}).get("component", "all"))
            if component == "tts" and hasattr(self._launcher_service, "schedule_recover"):
                try:
                    recovery = self._launcher_service.schedule_recover("tts")
                except (ValueError, RuntimeError):
                    raise HTTPException(status_code=503, detail="health.component_unavailable")
                return JSONResponse(status_code=202, content={**recovery, "status": "restarting"})
            try:
                recovery = await asyncio.to_thread(self._launcher_service.recover, component)
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")
            except RuntimeError:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            if component in {"asr", "tts", "embedding"}:
                components = ["asr", "tts", "embedding"]
            else:
                components = [component] if component != "all" else ["llm", "asr", "tts", "avatar", "embedding"]
            probes = {}
            for name in components:
                probes[name] = await asyncio.to_thread(self._aggregator.probe_component, name)
            ready = all(item.get("status") == "ready" for item in probes.values())
            return {**recovery, "status": "ready" if ready else "degraded", "probes": probes}

        # ── B4 memory management ─────────────────────────────────────
        @app.get("/api/v1/memories")
        async def get_memories(q: str = ""):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            return {
                "items": await asyncio.to_thread(self._memory_service.list_or_search, q),
                "query": q,
            }

        @app.post("/api/v1/memories", status_code=201)
        async def post_memory(payload: dict):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                return await asyncio.to_thread(
                    self._memory_service.create_manual, str(payload.get("content", ""))
                )
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")

        @app.get("/api/v1/memory-candidates")
        async def get_memory_candidates():
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            return {"items": await asyncio.to_thread(self._memory_service.all_candidates)}

        @app.post("/api/v1/memory-candidates/confirm")
        async def confirm_memory_candidate(payload: dict):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                result = await asyncio.to_thread(
                    self._memory_service.confirm_candidate,
                    session_id=int(payload.get("session_id")),
                    turn_id=int(payload.get("turn_id")),
                    content=str(payload.get("content", "")),
                )
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="asset.invalid")
            if result is None:
                raise HTTPException(status_code=404, detail="memory.not_found")
            return result

        @app.post("/api/v1/memory-candidates/reject")
        async def reject_memory_candidate(payload: dict):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                rejected = await asyncio.to_thread(
                    self._memory_service.reject_candidate,
                    session_id=int(payload.get("session_id")),
                    turn_id=int(payload.get("turn_id")),
                    content=str(payload.get("content", "")),
                )
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="asset.invalid")
            if not rejected:
                raise HTTPException(status_code=404, detail="memory.not_found")
            return {"rejected": True}

        @app.patch("/api/v1/memories/{memory_id}")
        async def patch_memory(memory_id: int, payload: dict):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                result = await asyncio.to_thread(
                    self._memory_service.edit, memory_id, str(payload.get("content", ""))
                )
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")
            if result is None:
                raise HTTPException(status_code=404, detail="memory.not_found")
            return result

        @app.delete("/api/v1/memories/{memory_id}")
        async def delete_memory(memory_id: int):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            deleted = await asyncio.to_thread(self._memory_service.delete, memory_id)
            if not deleted:
                raise HTTPException(status_code=404, detail="memory.not_found")
            return {"id": memory_id, "deleted": True}

        @app.delete("/api/v1/memories")
        async def purge_memories(payload: dict | None = None):
            if self._memory_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            if (payload or {}).get("confirmation") != "PURGE_ALL":
                raise HTTPException(status_code=412, detail="memory.confirm_required")
            deleted = await asyncio.to_thread(self._memory_service.purge_all)
            return {"deleted": deleted, "confirmed": True}

        @app.get("/api/v1/onboarding/draft")
        async def get_onboarding_draft():
            if not self._repository:
                raise HTTPException(status_code=404, detail="repository_not_initialized")
            return self._repository.get_onboarding_draft().to_dict()

        @app.put("/api/v1/onboarding/draft")
        async def put_onboarding_draft(payload: dict):
            if not self._repository:
                raise HTTPException(status_code=404, detail="repository_not_initialized")
            draft = self._repository.get_onboarding_draft()
            draft.consent_granted = bool(payload.get("consent_granted", draft.consent_granted))
            if "step_completed" in payload:
                try:
                    draft.bump_step(int(payload["step_completed"]))
                except ValueError as e:
                    raise HTTPException(status_code=422, detail=f"asset.invalid: {e}")
            if "profile_draft_json" in payload:
                draft.profile_draft_json = payload["profile_draft_json"]
            if "settings_json" in payload:
                draft.settings_json = payload["settings_json"]
            self._repository.upsert_onboarding_draft(draft)
            return draft.to_dict()

        @app.get("/api/v1/consents")
        async def get_consents():
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            return {"items": await asyncio.to_thread(self._repository.list_consents)}

        @app.post("/api/v1/consents")
        async def grant_consent(payload: dict):
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                return await asyncio.to_thread(
                    self._repository.grant_consent,
                    str(payload.get("scope", "all")),
                    str(payload.get("policy_version", "v1")),
                )
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")

        @app.delete("/api/v1/consents/{scope}")
        async def revoke_consent(scope: str):
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                result = await asyncio.to_thread(self._repository.revoke_consent, scope)
                if scope in {"voice", "all"} and self._privacy_cache_clear is not None:
                    await asyncio.to_thread(self._privacy_cache_clear)
                return result
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")

        @app.get("/api/v1/profile")
        async def get_profile():
            if not self._repository:
                raise HTTPException(status_code=404, detail="repository_not_initialized")
            p = self._repository.get_profile()
            if p is None:
                raise HTTPException(status_code=404, detail="profile_not_found")
            return p.to_dict()

        @app.put("/api/v1/profile")
        async def put_profile(payload: dict):
            if not self._repository:
                raise HTTPException(status_code=404, detail="repository_not_initialized")
            from cyberwife.domain.profile import Profile

            existing = self._repository.get_profile()
            expected_version = int(payload.get("expected_version", existing.version if existing else 0))
            p = Profile(
                id=existing.id if existing else 1,
                name=payload.get("name", existing.name if existing else ""),
                user_nickname=payload.get("user_nickname", existing.user_nickname if existing else ""),
                persona=payload.get("persona", existing.persona if existing else ""),
                relationship_context=payload.get("relationship_context", existing.relationship_context if existing else ""),
                example_dialogue=payload.get("example_dialogue", existing.example_dialogue if existing else ""),
                version=expected_version,
            )
            if not p.name.strip() or not p.user_nickname.strip():
                raise HTTPException(status_code=422, detail="asset.invalid")
            try:
                saved = await asyncio.to_thread(self._repository.save_profile, p, expected_version)
            except ValueError as exc:
                if str(exc) == "asset.version_conflict":
                    raise HTTPException(status_code=409, detail="asset.version_conflict")
                raise
            return saved.to_dict()

        @app.get("/api/v1/assets/{kind}")
        async def list_assets(kind: str):
            if kind not in {"portrait", "voice"}:
                raise HTTPException(status_code=422, detail="asset.invalid")
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            return {"kind": kind, "items": await asyncio.to_thread(self._repository.list_asset_versions, kind)}

        @app.get("/api/v1/assets/{kind}/active/content")
        async def active_asset_content(kind: str):
            """Serve only the active, consented local asset; never accept a path."""
            if kind not in {"portrait", "voice"}:
                raise HTTPException(status_code=422, detail="asset.invalid")
            if not self._repository or not self._repository.consent_active(kind):
                raise HTTPException(status_code=403, detail="auth.consent_required")
            active = await asyncio.to_thread(self._repository.get_active_asset, kind)
            if active is None:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            if self._asset_store is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                target = self._asset_store.resolve(str(active["relative_path"]))
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")
            if not target.is_file():
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            return FileResponse(target, headers={"Cache-Control": "no-store, private"})

        @app.post("/api/v1/assets/{asset_id}/activate")
        async def activate_asset(asset_id: int):
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                asset = await asyncio.to_thread(self._repository.get_asset_version, asset_id)
                if asset is None:
                    raise KeyError(asset_id)
                if asset.get("kind") == "portrait" and self._avatar_asset_service is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="avatar.build_required",
                    )
                return await asyncio.to_thread(self._repository.activate_asset, asset_id)
            except PermissionError:
                raise HTTPException(status_code=403, detail="auth.consent_required")
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")

        @app.post("/api/v1/assets/{asset_id}/avatar-builds", status_code=202)
        async def create_avatar_build(asset_id: int, background_tasks: BackgroundTasks):
            if self._avatar_asset_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                row = await asyncio.to_thread(
                    self._avatar_asset_service.create_build, asset_id, engine="wav2lip"
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            if row["status"] not in {"ready", "active", "building"}:
                background_tasks.add_task(
                    self._avatar_asset_service.run_build, int(row["id"])
                )
            return self._avatar_asset_service.public_record(row)

        @app.get("/api/v1/avatar-builds/{derivative_id}")
        async def get_avatar_build(derivative_id: int):
            if self._avatar_asset_service is None or not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            row = await asyncio.to_thread(
                self._repository.get_avatar_derivative, derivative_id
            )
            if row is None:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            return self._avatar_asset_service.public_record(row)

        @app.post("/api/v1/avatar-builds/{derivative_id}/idle-generation", status_code=202)
        async def start_idle_generation(derivative_id: int, background_tasks: BackgroundTasks):
            if self._avatar_asset_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                job = await asyncio.to_thread(
                    self._avatar_asset_service.queue_idle_generation, derivative_id
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            except RuntimeError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            if job["status"] in {"queued", "generating"}:
                background_tasks.add_task(
                    self._avatar_asset_service.run_idle_generation, derivative_id
                )
            return job

        @app.get("/api/v1/avatar-builds/{derivative_id}/idle-generation")
        async def get_idle_generation(derivative_id: int):
            if self._avatar_asset_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                return await asyncio.to_thread(
                    self._avatar_asset_service.get_idle_generation, derivative_id
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")

        @app.get("/api/v1/avatar-builds/{derivative_id}/idle-generation/{kind}")
        async def get_idle_preview(derivative_id: int, kind: str):
            if self._avatar_asset_service is None or kind not in {
                "frontal", "video", "intro", "outro",
            }:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            try:
                target = await asyncio.to_thread(
                    self._avatar_asset_service.idle_preview_path, derivative_id, kind
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")
            media_type = "image/png" if kind == "frontal" else "video/mp4"
            return FileResponse(
                target,
                media_type=media_type,
                headers={"Cache-Control": "no-store, private"},
            )

        @app.post("/api/v1/avatar-builds/{derivative_id}/idle-generation/approve")
        async def approve_idle_generation(derivative_id: int):
            if self._avatar_asset_service is None:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                row = await asyncio.to_thread(
                    self._avatar_asset_service.approve_idle_generation, derivative_id
                )
            except PermissionError:
                raise HTTPException(status_code=403, detail="auth.consent_required")
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            return self._avatar_asset_service.public_record(row)

        @app.get("/api/v1/avatar-builds/{derivative_id}/idle-generation/scenes/{scene_id}")
        async def get_idle_scene_preview(derivative_id: int, scene_id: str):
            if self._avatar_asset_service is None:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            try:
                target = await asyncio.to_thread(
                    self._avatar_asset_service.idle_scene_preview_path,
                    derivative_id,
                    scene_id,
                )
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            except ValueError:
                raise HTTPException(status_code=422, detail="asset.invalid")
            return FileResponse(
                target,
                media_type="video/mp4",
                headers={"Cache-Control": "no-store, private"},
            )

        @app.post("/api/v1/avatar-builds/{derivative_id}/activate")
        async def activate_avatar_build(derivative_id: int):
            if self._avatar_asset_service is None or not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                row = await asyncio.to_thread(
                    self._repository.activate_avatar_derivative, derivative_id
                )
            except PermissionError:
                raise HTTPException(status_code=403, detail="auth.consent_required")
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            return self._avatar_asset_service.public_record(row)

        @app.get("/api/v1/avatar/active")
        async def get_active_avatar():
            if self._avatar_asset_service is None or not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            row = await asyncio.to_thread(self._repository.get_active_avatar_derivative)
            if row is None:
                return {
                    "status": "legacy_fallback",
                    "engine": "wav2lip",
                    "avatar_id": "wav2lip256_avatar1",
                    "source_sha256": None,
                }
            return self._avatar_asset_service.public_record(row)

        @app.post("/api/v1/assets/{kind}/restore")
        async def restore_asset(kind: str):
            if kind not in {"portrait", "voice"}:
                raise HTTPException(status_code=422, detail="asset.invalid")
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            try:
                if kind == "portrait" and self._avatar_asset_service is not None:
                    row = await asyncio.to_thread(
                        self._repository.restore_previous_avatar_derivative
                    )
                    return self._avatar_asset_service.public_record(row)
                return await asyncio.to_thread(self._repository.restore_previous_asset, kind)
            except PermissionError:
                raise HTTPException(status_code=403, detail="auth.consent_required")
            except KeyError:
                raise HTTPException(status_code=404, detail="audit.entity_not_found")

        @app.get("/api/v1/audit")
        async def get_audit(entity: str = "", action: str = ""):
            if not self._repository:
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            rows = await asyncio.to_thread(
                self._repository.list_audit_events,
                entity=entity,
                action=action,
                limit=200,
            )
            return {"items": rows}

        # ── M2-stretch：资产上传/录音（multipart）────────────────────────
        @app.post("/api/v1/assets/{kind}/preview")
        async def upload_asset_preview(kind: str, file: UploadFile = File(...)):
            """multipart 上传：file=<binary> → {entity_id_hash, mime, size_bytes}。

            FR-04/05 写真/声纹资产 M2-stretch 接入；entity_id_hash 替代字面路径。
            """
            if kind not in {"portrait", "voice"}:
                raise HTTPException(status_code=422, detail="asset.invalid: bad kind")
            if self._repository is None or not self._repository.consent_active(kind):
                raise HTTPException(status_code=403, detail="auth.consent_required")
            if file is None or not file.filename:
                raise HTTPException(status_code=422, detail="asset.invalid: no file")
            import tempfile
            from pathlib import Path as _P
            content = await file.read()
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="asset.too_large")
            with tempfile.NamedTemporaryFile(delete=False, suffix=_P(file.filename).suffix) as tmp:
                tmp.write(content)
                tmp_path = _P(tmp.name)
            try:
                if self._asset_store is None:
                    raise HTTPException(status_code=503, detail="health.component_unavailable")
                original_name = _P(file.filename).name
                stored_name = f"{uuid.uuid4().hex}{_P(original_name).suffix.lower()}"
                meta = self._asset_store.ingest(kind, stored_name, tmp_path)
                meta["filename_or_revision"] = original_name
                mime = meta["mime"]
                meta = await asyncio.to_thread(self._repository.create_asset_version, meta)
                meta["mime"] = mime
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"asset.invalid: {e}")
            finally:
                tmp_path.unlink(missing_ok=True)
            return meta

        @app.post("/api/v1/assets/{kind}/record")
        async def upload_asset_record(kind: str, payload: dict):
            """前端 MediaRecorder blob 二进制 → 后端 ingest。

            payload = {"filename": "voice_clip.wav", "data_b64": "..."}
            """
            if kind not in {"portrait", "voice"}:
                raise HTTPException(status_code=422, detail="asset.invalid: bad kind")
            if self._repository is None or not self._repository.consent_active(kind):
                raise HTTPException(status_code=403, detail="auth.consent_required")
            import base64
            import tempfile
            from pathlib import Path as _P
            filename = payload.get("filename", "recording.wav")
            data_b64 = payload.get("data_b64", "")
            try:
                content = base64.b64decode(data_b64)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"asset.invalid: b64 decode failed: {e}")
            if len(content) > 50 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="asset.too_large")
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                tmp.write(content)
                tmp_path = _P(tmp.name)
            try:
                if self._asset_store is None:
                    raise HTTPException(status_code=503, detail="health.component_unavailable")
                original_name = _P(filename).name
                stored_name = f"{uuid.uuid4().hex}{_P(original_name).suffix.lower()}"
                meta = self._asset_store.ingest(kind, stored_name, tmp_path)
                meta["filename_or_revision"] = original_name
                mime = meta["mime"]
                meta = await asyncio.to_thread(self._repository.create_asset_version, meta)
                meta["mime"] = mime
            except ValueError as e:
                raise HTTPException(status_code=422, detail=f"asset.invalid: {e}")
            finally:
                tmp_path.unlink(missing_ok=True)
            return meta

        # ── B1 session lifecycle ─────────────────────────────────────
        @app.post("/api/v1/sessions")
        async def create_session(payload: dict | None = None):
            recording_policy = (payload or {}).get("recording_policy", "standard")
            if recording_policy not in {"standard", "none"}:
                raise HTTPException(status_code=422, detail="session.recording_policy_invalid")
            if recording_policy == "none":
                session = self._orchestrator.open_session("none")
                session_ref = register_private_ref(session.id)
                response_id = "0"
            elif self._repository is not None:
                session_id = await asyncio.to_thread(
                    self._repository.create_session, recording_policy
                )
                session = self._orchestrator.open_session(recording_policy, session_id=session_id)
                session_ref = str(session.id)
                response_id = str(session.id)
            else:
                session = self._orchestrator.open_session(recording_policy)
                session_ref = str(session.id)
                response_id = str(session.id)
            self._orchestrator.transition(session.id, SessionState.LISTENING)
            return {
                "id": response_id,
                "session_ref": session_ref,
                "state": session.state.value,
                "recording_policy": session.recording_policy.value,
                "next_turn_id": self._orchestrator.next_turn_id(session.id),
                "ws_url": f"/ws/v1/sessions/{session_ref}",
            }

        @app.patch("/api/v1/sessions/{session_ref}/no_record")
        async def enable_no_record(session_ref: str):
            session_id = resolve_session_ref(session_ref)
            if session_id is None:
                raise HTTPException(status_code=404, detail="session.not_found")
            session = self._orchestrator.get(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session.not_found")
            if session.recording_policy == RecordingPolicy.NONE:
                token = public_ref(session_id)
                return {"id": "0", "session_ref": token, "recording_policy": "none", "already_enabled": True}
            if self._memory_service is None:
                # Never flip the public policy unless compensating erasure is
                # available.  A partial success would be a false privacy claim.
                raise HTTPException(status_code=503, detail="health.component_unavailable")
            self._orchestrator.enable_no_record(session_id)
            runtime = self._session_runtimes.get(session_id)
            if runtime is not None and session.active_turn is not None:
                await runtime.interrupt(
                    reason="no_record",
                    expected_turn_id=session.active_turn.id,
                )
            try:
                deleted = await asyncio.to_thread(self._memory_service.enable_no_record, session_id)
            except Exception:
                # Purge is transactional. Revert the in-memory policy so the
                # caller can retry without leaving an ambiguous half-state.
                session.recording_policy = RecordingPolicy.STANDARD
                raise HTTPException(status_code=500, detail="internal.error")
            token = register_private_ref(session_id)
            return {
                "id": "0",
                "session_ref": token,
                "ws_url": f"/ws/v1/sessions/{token}",
                "recording_policy": "none",
                "deleted": deleted,
            }

        @app.delete("/api/v1/sessions/{session_ref}")
        async def delete_session(session_ref: str):
            session_id = resolve_session_ref(session_ref)
            if session_id is None:
                raise HTTPException(status_code=404, detail="session.not_found")
            session = self._orchestrator.get(session_id)
            if session is None:
                raise HTTPException(status_code=404, detail="session.not_found")
            self._orchestrator.close_session(session_id)
            if self._turn_pipeline is not None:
                self._turn_pipeline.forget_session(session_id)
            if (
                self._repository is not None
                and session.recording_policy == RecordingPolicy.STANDARD
                and session.ended_at is not None
            ):
                await asyncio.to_thread(
                    self._repository.end_session, session_id, session.ended_at
                )
            memory_extraction = None
            if (
                self._memory_service is not None
                and session.recording_policy.value == "standard"
            ):
                memory_extraction = await asyncio.to_thread(
                    self._memory_service.extract_session, session_id
                )
            response = {
                "id": self._orchestrator.public_session_id(session_id),
                "state": "idle",
                "ended": True,
                "memory_extraction": memory_extraction,
            }
            if session.recording_policy == RecordingPolicy.NONE:
                forget_private_ref(session_id)
                self._orchestrator.drop_session(session_id)
            return response

        # ── B1 WebSocket PCM + control protocol ───────────────────────
        @app.websocket("/ws/v1/sessions/{session_ref}")
        async def ws_session(ws: WebSocket, session_ref: str):
            await ws.accept()
            session_id = resolve_session_ref(session_ref)
            if session_id is None:
                await ws.send_json({
                    "type": "error", "session_id": "0", "turn_id": None,
                    "event_seq": 0, "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "payload": error_envelope("session.not_found", "session not found"),
                })
                await ws.close(code=4404)
                return
            session = self._orchestrator.get(session_id)
            if session is None:
                await ws.send_json({
                    "type": "error", "session_id": self._orchestrator.public_session_id(session_id), "turn_id": None,
                    "event_seq": 0, "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "payload": error_envelope("session.not_found", "session not found"),
                })
                await ws.close(code=4404)
                return
            audio = bytearray()
            expected_chunk_seq = 0
            last_client_event_seq = 0
            runtime = SessionRuntime(session_id, ws, self._orchestrator, self._turn_pipeline)
            await runtime.start()
            self._session_runtimes[session_id] = runtime

            async def send_error(code: str, message: str, turn_id: int | None = None) -> None:
                event = self._orchestrator.emit(
                    session_id,
                    "error",
                    turn_id=turn_id,
                    payload=error_envelope(code, message),
                )
                if event:
                    await runtime.send(event, priority=True)

            initial = self._orchestrator.emit(
                session_id,
                "state.changed",
                payload={"previous": "idle", "current": session.state.value, "reason": "ws_connected"},
            )
            if initial:
                await runtime.send(initial)
            try:
                while True:
                    message = await ws.receive()
                    if message.get("type") == "websocket.disconnect":
                        break
                    frame = message.get("bytes")
                    if frame is not None:
                        if len(frame) > 4096:
                            await send_error("frame.size_limit", "binary frame exceeds 4KB")
                            await ws.close(code=1009)
                            return
                        if len(frame) != 646:
                            await send_error("frame.size_limit", "binary audio frame must be 646 bytes")
                            continue
                        turn_id, chunk_seq = struct.unpack_from("<IH", frame, 0)
                        expected_turn = self._orchestrator.next_turn_id(session_id)
                        if turn_id != expected_turn or chunk_seq != expected_chunk_seq:
                            await send_error("turn.late_event", "out-of-order or cross-turn audio frame", turn_id)
                            continue
                        if len(audio) + 640 > 16000 * 2 * 30:
                            await send_error("frame.size_limit", "utterance exceeds 30 seconds", turn_id)
                            audio.clear()
                            expected_chunk_seq = 0
                            continue
                        audio.extend(frame[6:])
                        expected_chunk_seq += 1
                        continue
                    text = message.get("text")
                    if text is None:
                        continue
                    try:
                        control = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        await send_error("internal.error", "invalid JSON control frame")
                        continue
                    if not isinstance(control, dict) or not isinstance(control.get("type"), str):
                        await send_error("internal.error", "control frame requires type")
                        continue
                    client_seq = control.get("event_seq")
                    if client_seq is not None:
                        if not isinstance(client_seq, int) or client_seq <= last_client_event_seq:
                            await send_error("turn.late_event", "client event_seq must increase")
                            continue
                        last_client_event_seq = client_seq
                    event_type = control["type"]
                    if event_type == "ping":
                        await runtime.send({"type": "pong"}, priority=True)
                    elif event_type == "audio.silence":
                        turn_id = int(control.get("turn_id", self._orchestrator.next_turn_id(session_id)))
                        if turn_id != self._orchestrator.next_turn_id(session_id):
                            await send_error("turn.late_event", "silence marker belongs to another turn", turn_id)
                            continue
                        if not audio:
                            await send_error("frame.size_limit", "silence marker has no audio", turn_id)
                            continue
                        if self._turn_pipeline is None:
                            await send_error("health.component_unavailable", "turn pipeline unavailable", turn_id)
                            audio.clear()
                            expected_chunk_seq = 0
                            continue
                        pcm = bytes(audio)
                        audio.clear()
                        expected_chunk_seq = 0
                        accepted = await runtime.start_turn(turn_id, pcm)
                        if not accepted:
                            await send_error("turn.late_event", "session already has an active turn", turn_id)
                    elif event_type == "barge_in.detected":
                        try:
                            expected_turn_id = int(control["turn_id"])
                        except (KeyError, TypeError, ValueError):
                            expected_turn_id = None
                        await runtime.interrupt(
                            reason="barge_in",
                            expected_turn_id=expected_turn_id,
                        )
                    elif event_type == "conversation.stop":
                        self._orchestrator.close_session(session_id)
                        if self._turn_pipeline is not None:
                            self._turn_pipeline.forget_session(session_id)
                        if (
                            self._repository is not None
                            and session.recording_policy == RecordingPolicy.STANDARD
                            and session.ended_at is not None
                        ):
                            await asyncio.to_thread(
                                self._repository.end_session, session_id, session.ended_at
                            )
                        if (
                            self._memory_service is not None
                            and session.recording_policy.value == "standard"
                        ):
                            await asyncio.to_thread(
                                self._memory_service.extract_session, session_id
                            )
                        await ws.close(code=1000)
                        return
                    elif event_type == "audio.playback.started":
                        if self._turn_pipeline is None:
                            await send_error(
                                "health.component_unavailable",
                                "turn pipeline unavailable",
                                int(control.get("turn_id", 0)),
                            )
                            continue
                        try:
                            accepted = self._turn_pipeline.confirm_playback(
                                trace_id=str(control["trace_id"]),
                                session_id=session_id,
                                turn_id=int(control["turn_id"]),
                                generation=int(control["generation"]),
                                asr_to_playback_ms=float(control["asr_to_playback_ms"]),
                                browser_first_non_silent_wall_ms=float(
                                    control["browser_first_non_silent_wall_ms"]
                                ),
                            )
                        except (KeyError, TypeError, ValueError):
                            accepted = False
                        if not accepted:
                            await send_error(
                                "turn.late_event",
                                "playback confirmation is duplicate, unknown, or stale",
                                int(control.get("turn_id", 0)),
                            )
                    elif event_type == "audio.playback.ended":
                        if self._turn_pipeline is None:
                            await send_error("health.component_unavailable", "turn pipeline unavailable")
                            continue
                        try:
                            completed = self._turn_pipeline.complete_playback(
                                session_id,
                                int(control["generation"]),
                            )
                        except (KeyError, TypeError, ValueError):
                            completed = None
                        if completed is None:
                            await send_error(
                                "turn.late_event",
                                "playback completion is unknown or stale",
                                int(control.get("turn_id", 0)),
                            )
                        else:
                            await runtime.send(completed, priority=True)
                    elif event_type in {"audio.level", "audio.device_lost", "audio.device_back"}:
                        continue
                    else:
                        await send_error("internal.error", "unsupported control event")
            except WebSocketDisconnect:
                pass
            finally:
                await runtime.close()
                if self._session_runtimes.get(session_id) is runtime:
                    self._session_runtimes.pop(session_id, None)
                if session.recording_policy == RecordingPolicy.NONE and session.state == SessionState.IDLE:
                    forget_private_ref(session_id)
                    self._orchestrator.drop_session(session_id)

        # Register the release UI last so /api and /ws routes above retain
        # precedence. V1 therefore needs no separate Vite development server.
        index_path = self._static_root / "index.html"
        if index_path.is_file():
            app.mount("/", StaticFiles(directory=self._static_root, html=True), name="release-ui")
        else:
            @app.get("/")
            async def release_ui_missing() -> JSONResponse:
                return JSONResponse(
                    status_code=503,
                    content=error_envelope(
                        "health.component_unavailable",
                        "frontend release build missing; run npm run build in prototype",
                    ),
                )

        return app
