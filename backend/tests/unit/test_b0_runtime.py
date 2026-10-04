from datetime import datetime, timezone
from pathlib import Path

from cyberwife.application.functional_probes import FunctionalProbeRunner, ProbeResult
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.runtime_config import load_runtime_config, normalize_local_path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_runtime_config_merges_local_over_defaults():
    config = load_runtime_config(REPO_ROOT, REPO_ROOT / "config" / "runtime.local.toml")
    assert config["server"]["gateway_port"] == 7860
    assert config["paths"]["data_root"] == "/home/administrator/.cyberWife"
    assert config["db"]["path"] == "/home/administrator/.cyberWife/cyberwife.db"
    assert config["models"]["tts"] == "cosyvoice2-0.5b"


def test_windows_path_normalizes_in_wsl():
    assert normalize_local_path(r"C:\models\a.gguf") == "/mnt/c/models/a.gguf"


def test_manifest_verified_is_not_runtime_ready():
    registry = ModelRegistry(REPO_ROOT)
    assert registry.health_for("llm").status == "loading"
    assert registry.health_for("llm").last_error == "probe_not_run"


def test_real_probe_result_promotes_component_to_ready():
    registry = ModelRegistry(REPO_ROOT)
    result = ProbeResult(
        component="llm",
        status="ready",
        latency_ms=12,
        checked_at=datetime.now(timezone.utc),
        logical_id="qwen3-14b-instruct-q4_k_m",
        device="cuda",
        dtype="q4_k_m",
    )
    registry.record_probe(result)
    health = registry.health_for("llm")
    assert health.status == "ready"
    assert health.latency_ms == 12


def test_fallback_probe_is_degraded_and_explicit():
    registry = ModelRegistry(REPO_ROOT)
    result = ProbeResult(
        component="tts",
        status="degraded",
        latency_ms=20,
        checked_at=datetime.now(timezone.utc),
        logical_id="qwen3-tts-12hz-1.7b-base",
        device="cuda",
        dtype="bf16",
        evidence={"fallback_active": True},
    )
    registry.record_probe(result)
    health = registry.health_for("tts")
    assert health.status == "degraded"
    assert health.fallback_active is True
    assert registry.overall_status() == "degraded"


def test_verified_probe_evidence_normalizes_to_runtime_ready(monkeypatch):
    runner = FunctionalProbeRunner(REPO_ROOT, speech_url=None)
    monkeypatch.setattr(runner, "_probe_module", lambda module: {
        "status": "verified", "logical_id": "silero-vad-v5",
    })
    result = runner.run("vad")
    assert result.status == "ready"


def test_failed_probe_never_promotes_ready(tmp_path):
    registry = ModelRegistry(REPO_ROOT)
    runner = FunctionalProbeRunner(
        REPO_ROOT,
        injected={"llm": lambda: ProbeResult(
            component="llm",
            status="error",
            latency_ms=2,
            checked_at=datetime.now(timezone.utc),
            error="broken fixture",
        )},
    )
    aggregator = HealthAggregator(registry, runner, data_root=tmp_path)
    health = aggregator.probe_component("llm")
    assert health["status"] == "error"
    assert health["last_error"] == "broken fixture"


def test_resource_snapshot_contains_real_ram_and_disk(tmp_path):
    registry = ModelRegistry(REPO_ROOT)
    resources = HealthAggregator(registry, data_root=tmp_path).snapshot()["resources"]
    assert resources["ram_total_gb"] > 0
    assert resources["ram_used_gb"] >= 0
    assert resources["disk_free_gb"] > 0
