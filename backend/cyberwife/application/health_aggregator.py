"""HealthAggregator — 聚合组件状态与资源快照。

按 implementation-contracts §18 / target-architecture §9。
M1 阶段不实际探测进程；返回基于 ModelRegistry 状态的聚合。
"""
from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from cyberwife.application.functional_probes import FunctionalProbeRunner, ProbeResult
from cyberwife.application.model_registry import ComponentHealth, ModelRegistry


class HealthAggregator:
    def __init__(
        self,
        registry: ModelRegistry,
        probe_runner: FunctionalProbeRunner | None = None,
        data_root: Path | None = None,
    ) -> None:
        self._registry = registry
        self._probe_runner = probe_runner
        self._data_root = data_root or Path("/")

    @property
    def supports_functional_probes(self) -> bool:
        return self._probe_runner is not None

    def snapshot(self) -> dict:
        """返回符合 schemas/rest/health.schema.json 的 dict。"""
        if self._probe_runner is not None:
            for component in self._registry.all_components():
                if not self._probe_runner.liveness(component):
                    self._registry.record_probe(ProbeResult(
                        component=component, status="error", latency_ms=0,
                        checked_at=datetime.now(timezone.utc), error="runtime_unreachable",
                    ))
        components = self._registry.all_health()
        return {
            "status": self._registry.overall_status(),
            "components": {
                cid: self._component_to_dict(h) for cid, h in components.items()
            },
            "resources": self._resources(),
            "version": {
                "app": "cyberwife-1.0.0",
                "schema": "1.0.0",
            },
        }

    def _component_to_dict(self, h: ComponentHealth) -> dict:
        d = {
            "status": h.status,
            "logical_id": h.logical_id,
            "last_probe": h.last_probe.isoformat(),
        }
        if h.last_error:
            d["last_error"] = h.last_error
        if h.revision:
            d["revision"] = h.revision
        if h.device:
            d["device"] = h.device
        if h.dtype:
            d["dtype"] = h.dtype
        if h.latency_ms is not None:
            d["latency_ms"] = h.latency_ms
        d["fallback_active"] = h.fallback_active
        return d

    def probe_component(self, component: str) -> dict:
        if component not in self._registry.all_components():
            raise KeyError(component)
        if self._probe_runner is None:
            raise RuntimeError("functional_probe_runner_not_configured")
        result = self._probe_runner.run(component)
        return self._component_to_dict(self._registry.record_probe(result))

    def _resources(self) -> dict:
        """Read actual device, system memory and configured data-volume capacity."""
        try:
            usage = shutil.disk_usage(self._data_root)
            disk_free_gb = round(usage.free / 1024 ** 3, 2)
        except Exception:
            usage = shutil.disk_usage("/")
            disk_free_gb = round(usage.free / 1024 ** 3, 2)
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_pages = os.sysconf("SC_PHYS_PAGES")
        available_pages = os.sysconf("SC_AVPHYS_PAGES")
        ram_total = total_pages * page_size / 1024 ** 3
        ram_available = available_pages * page_size / 1024 ** 3
        resources = {
            "ram_used_gb": round(ram_total - ram_available, 2),
            "ram_total_gb": round(ram_total, 2),
            "disk_free_gb": disk_free_gb,
            "cache_writes_allowed": disk_free_gb >= 10.0,
            "storage_pressure": "normal" if disk_free_gb >= 10.0 else "low",
        }
        try:
            completed = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            used, total = [float(value.strip()) / 1024 for value in completed.stdout.splitlines()[0].split(",")]
            resources["vram_used_gb"] = round(used, 2)
            resources["vram_total_gb"] = round(total, 2)
        except Exception:
            pass
        return resources
