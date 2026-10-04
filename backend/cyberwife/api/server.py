"""M2-stretch + Q3T 后端服务入口。

启动方式：python -m cyberwife.api.server [--host 127.0.0.1] [--port 7860]
                                          [--assets-root PATH]
                                          [--db PATH]

ADR-006 修订（2026-09-23）：写真/声音默认放 C:\\workSpace\\cyberWife\\assets\\
（用户在 2026-09-23 显式选择 A 方案）；通过 .gitignore 强化与人 .consent-backup 隔离。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import sys
import time
import wave
from pathlib import Path

import uvicorn

# 把 backend 加进 sys.path
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_BACKEND_ROOT))

from cyberwife.application.api_gateway import ApiGateway  # noqa: E402
from cyberwife.application.health_aggregator import HealthAggregator  # noqa: E402
from cyberwife.application.functional_probes import FunctionalProbeRunner  # noqa: E402
from cyberwife.application.model_registry import ModelRegistry  # noqa: E402
from cyberwife.application.runtime_config import load_runtime_config, normalize_local_path  # noqa: E402
from cyberwife.application.conversation_orchestrator import ConversationOrchestrator  # noqa: E402
from cyberwife.application.turn_pipeline import TurnPipeline  # noqa: E402
from cyberwife.application.prompt_compiler import PromptCompiler  # noqa: E402
from cyberwife.application.output_sanitizer import OutputSanitizer  # noqa: E402
from cyberwife.adapters.llama_cpp_adapter import LlamaCppAdapter  # noqa: E402
from cyberwife.adapters.speech_runtime_client import SpeechRuntimeClient  # noqa: E402
from cyberwife.adapters.cosyvoice_tts_adapter import CosyVoiceTtsAdapter  # noqa: E402
from cyberwife.adapters.qwen_tts_adapter import QwenTtsAdapter  # noqa: E402
from cyberwife.adapters.live_talking_adapter import LiveTalkingAdapter  # noqa: E402
from cyberwife.application.media_pipeline import MediaPipeline  # noqa: E402
from cyberwife.application.warm_response_cache import WarmResponseCache  # noqa: E402
from cyberwife.domain.warm_response import WarmResponseContext, WarmResponsePolicy  # noqa: E402
from cyberwife.infrastructure.sqlite_repository import SqliteRepository  # noqa: E402
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository  # noqa: E402
from cyberwife.adapters.speech_embedding_adapter import SpeechEmbeddingAdapter  # noqa: E402
from cyberwife.application.memory_service import MemoryService  # noqa: E402
from cyberwife.application.retention_service import RetentionService  # noqa: E402
from cyberwife.application.launcher_service import LauncherService  # noqa: E402
from cyberwife.application.avatar_asset_service import AvatarAssetService  # noqa: E402
from cyberwife.application.runtime_metrics import RuntimeMetrics  # noqa: E402
from cyberwife.infrastructure.asset_store import AssetStore  # noqa: E402
from cyberwife.infrastructure.structured_logger import StructuredLogger  # noqa: E402


# ADR-006 修订后默认资产根（Windows 端）
DEFAULT_DATA_ROOT = Path.home() / ".cyberWife"
DEFAULT_ASSETS_ROOT = DEFAULT_DATA_ROOT / "assets"


def _probe_tts(tts, logical_id: str, reference_audio: str, reference_text: str) -> dict:
    started = time.perf_counter()
    frames = list(tts.synthesize_stream("你好。", reference_audio, reference_text, max_duration_s=5.0))
    non_silent = sum(sum(byte != 0 for byte in frame) for frame in frames)
    if not frames or non_silent == 0:
        raise RuntimeError("loaded TTS produced no non-silent audio")
    return {
        "status": "degraded" if os.environ.get("CW_TTS_FALLBACK_ACTIVE") == "1" else "ready",
        "logical_id": logical_id,
        "fallback_active": os.environ.get("CW_TTS_FALLBACK_ACTIVE") == "1",
        "device": "cuda", "dtype": "fp16" if logical_id == "cosyvoice2-0.5b" else "bf16",
        "frame_count": len(frames), "non_silent_bytes": non_silent,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="cyberWife V1 API Gateway")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--config", default=str(_REPO_ROOT / "config" / "runtime.local.toml"))
    parser.add_argument("--db", default=None, help="SQLite 数据库路径")
    parser.add_argument(
        "--assets-root",
        default=None,
        help="写真/声音资产根目录（默认读取 runtime TOML 的 ext4 路径）",
    )
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("Gateway must bind loopback")
    repo_root = _REPO_ROOT
    runtime = load_runtime_config(repo_root, Path(normalize_local_path(args.config)))
    paths = runtime.get("paths", {})
    data_root = Path(paths.get("data_root", DEFAULT_DATA_ROOT))
    assets_root = Path(args.assets_root or paths.get("assets_root", DEFAULT_ASSETS_ROOT))
    configured_db = runtime.get("db", {}).get("path")
    if configured_db == "/mnt/cw-data/cyberwife.db" and str(data_root) != "/mnt/cw-data":
        configured_db = str(data_root / "cyberwife.db")
    db_path = Path(args.db or configured_db or data_root / "cyberwife.db")
    for path in (data_root, assets_root, db_path.parent, data_root / "logs", data_root / "audit"):
        path.mkdir(parents=True, exist_ok=True)
    repo = SqliteRepository(db_path, schema_sql_path=repo_root / "migrations" / "0001_init.sql")
    registry = ModelRegistry(repo_root)
    server = runtime.get("server", {})
    llama_host = str(server.get("llama_host", "127.0.0.1"))
    if llama_host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("LLM endpoint must be loopback")
    probes = FunctionalProbeRunner(
        repo_root,
        llama_url=f"http://{llama_host}:{server.get('llama_port', 8090)}",
        speech_url=f"http://127.0.0.1:{server.get('speech_port', 8091)}",
        avatar_url=f"http://127.0.0.1:{server.get('avatar_port', 8010)}",
    )
    aggregator = HealthAggregator(registry, probes, data_root=data_root)
    orchestrator = ConversationOrchestrator()
    speech_client = SpeechRuntimeClient(
        f"http://127.0.0.1:{server.get('speech_port', 8091)}",
        timeout_s=120.0,
    )
    embedding = SpeechEmbeddingAdapter(
        f"http://127.0.0.1:{server.get('speech_port', 8091)}", timeout_s=120.0
    )
    memory_repository = SqliteMemoryRepository(repo.conn, repo.lock)
    memory_service = MemoryService(repo, memory_repository, embedding)
    retention_service = RetentionService(repo, data_root=data_root)
    launcher_service = LauncherService(repo_root)
    asset_store = AssetStore(assets_root)
    avatar_asset_service = AvatarAssetService(
        repo,
        asset_store=asset_store,
        avatar_root=data_root / "avatar" / "avatars",
    )
    llm = LlamaCppAdapter(
        host=llama_host,
        port=int(server.get("llama_port", 8090)),
        timeout_s=60.0,
    )
    configured_tts = os.environ.get(
        "CW_TTS_MODEL",
        runtime.get("models", {}).get("tts", "qwen3-tts-12hz-1.7b-base"),
    )
    cosyvoice_load_trt = os.environ.get("CW_COSYVOICE_LOAD_TRT", "0") == "1"
    tts_entry = registry.get(configured_tts)
    if tts_entry is None:
        raise SystemExit(f"TTS registry entry is required: {configured_tts}")
    if configured_tts == "cosyvoice2-0.5b":
        cosyvoice_source = os.environ.get(
            "CW_COSYVOICE_SOURCE_DIR",
            paths.get("cosyvoice_source", str(DEFAULT_DATA_ROOT / "src" / "CosyVoice")),
        )
        tts = CosyVoiceTtsAdapter(
            tts_entry.absolute_path,
            source_dir=cosyvoice_source,
            fp16=True,
            stream=True,
            load_trt=cosyvoice_load_trt,
        )
    else:
        tts = QwenTtsAdapter(tts_entry.absolute_path, device="cuda", dtype="bf16")
    media_pipeline = MediaPipeline(
        tts,
        LiveTalkingAdapter(f"http://127.0.0.1:{server.get('avatar_port', 8010)}"),
    )

    def profile_provider() -> dict:
        profile = repo.get_profile()
        if profile is None:
            return {
                "name": "数字伴侣",
                "user_nickname": "你",
                "persona": "温柔、自然、真诚",
                "relationship_context": "你们正在进行私人日常对话",
            }
        return profile.to_dict()

    compiler = PromptCompiler()
    sanitizer = OutputSanitizer()
    fallback_reference_audio = str(repo_root / "assets" / "voice" / "user_clip_v2.wav")
    fallback_reference_text = "早上好，宝贝，快起床了，起来陪我玩"

    def voice_reference_provider() -> tuple[str, str]:
        """Resolve the active, consented local voice for every new TTS job."""
        active = repo.get_active_asset("voice") if repo.consent_active("voice") else None
        draft = repo.get_onboarding_draft()
        transcript = str(draft.settings_json.get("voice_transcript", "")).strip()
        if active is not None:
            candidate = (repo_root / "assets" / str(active["relative_path"])).resolve()
            assets_root = (repo_root / "assets").resolve()
            if candidate.is_relative_to(assets_root) and candidate.is_file() and transcript:
                return str(candidate), transcript
        return fallback_reference_audio, fallback_reference_text

    # Readiness means the expensive models are warm, not merely imported.
    # This moves the one-time cold cost into one-click startup rather than the
    # user's first intimate conversation turn.
    warm_prompt = compiler.to_chatml(compiler.compile(profile=profile_provider(), user_input="你好"))
    list(llm.generate_stream(warm_prompt, max_tokens=1, temperature=0.0, stop=["<|im_end|>"]))
    warm_started = time.perf_counter()
    reference_audio, reference_text = voice_reference_provider()
    warm_frames = list(tts.synthesize_stream("你好。", reference_audio, reference_text, max_duration_s=5.0))
    if not warm_frames:
        raise SystemExit("TTS warm-up produced no audio")
    # The warm-up intentionally pays model cold cost before readiness, but its
    # host-side Torch/NumPy buffers are transient.  Release them before the
    # launcher declares Gateway healthy so the first AC-14 sample and the
    # user's idle post-start desktop reflect steady residency, not allocator
    # arenas that would otherwise persist until the first conversation ends.
    startup_cleanup = getattr(tts, "release_transient_memory", None)
    if startup_cleanup is not None:
        startup_cleanup()
    print(f"[cyberWife] TTS warm in {time.perf_counter() - warm_started:.1f}s")

    warm_policy = WarmResponsePolicy(("你好",), version="v1")
    warm_cache = WarmResponseCache(warm_policy)
    llm_entry = registry.get("qwen3-14b-instruct-q4_k_m")

    def warm_context_provider() -> WarmResponseContext:
        profile = profile_provider()
        current_audio, _ = voice_reference_provider()
        voice_digest = hashlib.sha256(Path(current_audio).read_bytes()).hexdigest()
        return WarmResponseContext(
            persona_version=str(profile.get("version", "default-v1")),
            voice_version=voice_digest,
            llm_revision=llm_entry.filename_or_revision if llm_entry else "unknown",
            tts_revision=tts_entry.filename_or_revision,
            policy_version=warm_policy.version,
        )

    if not warm_cache.put(
        "你好",
        warm_context_provider(),
        reply_text="你好。",
        pcm_frames=tuple(warm_frames),
    ):
        raise SystemExit("warm response seed was rejected")
    embedding_health = embedding.health()
    if embedding_health.get("status") != "ready":
        raise SystemExit(f"Embedding warm-up failed: {embedding_health.get('error', 'unknown')}")

    pipeline = TurnPipeline(
        orchestrator,
        speech_client,
        llm,
        compiler,
        sanitizer,
        repository=repo,
        profile_provider=profile_provider,
        media_pipeline=media_pipeline,
        voice_reference_provider=voice_reference_provider,
        first_playable_min_chars=int(
            os.environ.get(
                "CW_FIRST_PLAYABLE_MIN_CHARS",
                runtime.get("streaming", {}).get("first_playable_min_chars", 10),
            )
        ),
        warm_response_cache=warm_cache,
        warm_context_provider=warm_context_provider,
        memory_provider=memory_service.prompt_memories,
        runtime_metrics=RuntimeMetrics(),
        logger=StructuredLogger(name="cyberwife.turn_pipeline"),
    )

    def preview_tts(text: str) -> bytes:
        current_audio, current_text = voice_reference_provider()
        frames = list(
            tts.synthesize_stream(
                text,
                current_audio,
                current_text,
                max_duration_s=15.0,
            )
        )
        pcm = b"".join(frames)
        if not pcm:
            raise RuntimeError("TTS preview produced no audio")
        target = io.BytesIO()
        with wave.open(target, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(pcm)
        return target.getvalue()

    gateway = ApiGateway(
        registry,
        aggregator,
        repository=repo,
        assets_root=assets_root,
        asset_store=asset_store,
        orchestrator=orchestrator,
        turn_pipeline=pipeline,
        memory_service=memory_service,
        retention_service=retention_service,
        launcher_service=launcher_service,
        tts_probe=lambda: _probe_tts(tts, configured_tts, reference_audio, reference_text),
        tts_preview=preview_tts,
        shutdown_hooks=(pipeline.close, media_pipeline.close),
        avatar_asset_service=avatar_asset_service,
        privacy_cache_clear=getattr(tts, "clear_private_cache", None),
    )
    app = gateway.build_app()

    print(f"[cyberWife] Starting on {args.host}:{args.port}")
    print("  local_data=configured")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
