"""ModelRegistry — 模型注册与运行时元数据查询。

按 implementation-contracts §10 fallback 表与 §17 [models] 段合同。
仅读取 model-registry.local.yaml，不修改。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cyberwife.application.functional_probes import ProbeResult
from cyberwife.application.runtime_config import normalize_local_path

import yaml


@dataclass
class ModelEntry:
    logical_id: str
    component: str
    absolute_path: str
    filename_or_revision: str = ""
    size_bytes: int = 0
    sha256: Optional[str] = None
    license_id: str = "unknown"
    license_review: str = "pending"
    runtime: str = ""
    functional_probe: str = ""
    verified_at: Optional[str] = None
    status: str = "discovered"  # discovered|hashed|licensed|loadable|verified|blocked
    extra: dict = field(default_factory=dict)


@dataclass
class ComponentHealth:
    logical_id: str
    status: str  # ready|loading|degraded|error
    last_probe: datetime
    last_error: Optional[str] = None
    fallback_active: bool = False
    revision: Optional[str] = None
    device: Optional[str] = None
    dtype: Optional[str] = None
    latency_ms: Optional[int] = None


class ModelRegistry:
    """实现 ports/ModelRegistry 抽象（隐式）；M1 阶段未拆出抽象类，直接给应用层用。"""

    def __init__(self, local_path: Optional[Path] = None, example_path: Optional[Path] = None) -> None:
        # 如果调用方传入目录，按"该目录包含 config/"解析；若传入文件，直接使用
        # 默认从 REPO_ROOT/config 加载
        repo = Path(__file__).resolve().parents[3]
        if local_path is not None:
            if local_path.is_dir():
                local_path = local_path / "config" / "model-registry.local.yaml"
            self._local_path = Path(local_path)
        else:
            self._local_path = repo / "config" / "model-registry.local.yaml"
        if example_path is not None:
            if example_path.is_dir():
                example_path = example_path / "config" / "model-registry.example.yaml"
            self._example_path = Path(example_path)
        else:
            self._example_path = repo / "config" / "model-registry.example.yaml"
        self._entries: dict[str, ModelEntry] = {}
        self._probe_cache: dict[str, ComponentHealth] = {}
        self._load()

    def _load(self) -> None:
        path = self._local_path if self._local_path.exists() else self._example_path
        if not path.exists():
            return
        with path.open(encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        for entry in doc.get("models", []):
            logical_id = entry.get("logical_id")
            if not logical_id:
                continue
            abs_path = normalize_local_path(entry.get("absolute_path", "") or "")
            # 环境变量覆盖
            env_key = f"CW_MODEL_{logical_id.upper().replace('-', '_').replace('/', '_')}"
            if env_key in os.environ:
                abs_path = os.environ[env_key]
            self._entries[logical_id] = ModelEntry(
                logical_id=logical_id,
                component=entry.get("component", "unknown"),
                absolute_path=abs_path,
                filename_or_revision=entry.get("filename_or_revision", ""),
                size_bytes=int(entry.get("size_bytes", 0) or 0),
                sha256=entry.get("sha256"),
                license_id=entry.get("license_id", "unknown"),
                license_review=entry.get("license_review", "pending"),
                runtime=entry.get("runtime", ""),
                functional_probe=entry.get("functional_probe", ""),
                verified_at=entry.get("verified_at"),
                status=entry.get("status", "discovered"),
                extra={k: v for k, v in entry.items() if k not in {
                    "logical_id", "component", "absolute_path", "filename_or_revision",
                    "size_bytes", "sha256", "license_id", "license_review",
                    "runtime", "functional_probe", "verified_at", "status",
                }},
            )

    def get(self, logical_id: str) -> Optional[ModelEntry]:
        return self._entries.get(logical_id)

    def all(self) -> list[ModelEntry]:
        return list(self._entries.values())

    def all_components(self) -> list[str]:
        return ["vad", "asr", "llm", "tts", "avatar", "embedding"]

    def health_for(self, logical_id: str) -> ComponentHealth:
        """Return runtime health; manifest metadata never implies readiness.

        支持 logical_id（精确 key）和 component 名（vad/asr/llm/tts/avatar/embedding，
        取该 component 第一个匹配的 entry）。
        """
        if logical_id in self._probe_cache:
            return self._probe_cache[logical_id]

        entry = self._entries.get(logical_id)
        if entry is None:
            # 尝试按 component 名查找
            for e in self._entries.values():
                if e.component == logical_id:
                    entry = e
                    break
        if entry is None:
            return ComponentHealth(
                logical_id=logical_id,
                status="error",
                last_probe=datetime.now(timezone.utc),
                last_error="not_in_registry",
            )
        status = "error" if entry.status in {"blocked", "blocked_runtime"} else "loading"
        return ComponentHealth(
            logical_id=logical_id,
            status=status,
            last_probe=datetime.now(timezone.utc),
            last_error="manifest_blocked" if status == "error" else "probe_not_run",
            revision=entry.filename_or_revision or None,
            device="unknown",
            dtype="unknown",
        )

    def record_probe(self, result: ProbeResult) -> ComponentHealth:
        """Persist one runtime probe in memory for subsequent health snapshots."""
        health = ComponentHealth(
            logical_id=result.logical_id or result.component,
            status=result.status,
            last_probe=result.checked_at,
            last_error=result.error,
            revision=(self.get(result.logical_id).filename_or_revision if result.logical_id and self.get(result.logical_id) else None),
            device=result.device,
            dtype=result.dtype,
            latency_ms=result.latency_ms,
            fallback_active=bool((result.evidence or {}).get("fallback_active", False)),
        )
        self._probe_cache[result.component] = health
        if result.logical_id:
            self._probe_cache[result.logical_id] = health
        return health

    def all_health(self) -> dict[str, ComponentHealth]:
        return {logical_id: self.health_for(logical_id) for logical_id in self.all_components()}

    def overall_status(self) -> str:
        statuses = [h.status for h in self.all_health().values()]
        if any(s == "error" for s in statuses):
            return "error"
        if any(s == "degraded" for s in statuses):
            return "degraded"
        if any(s == "loading" for s in statuses):
            return "loading"
        return "ready"
