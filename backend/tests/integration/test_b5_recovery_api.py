from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.functional_probes import FunctionalProbeRunner, ProbeResult
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.launcher_service import LauncherService
from cyberwife.application.model_registry import ModelRegistry


ROOT = Path(__file__).resolve().parents[3]


class FakeLauncher:
    def __init__(self, fail=False): self.calls = []; self.fail = fail
    def recover(self, component="all"):
        self.calls.append(component)
        if self.fail: raise RuntimeError("recovery failed")
        managed = "gateway" if component == "tts" else "speech" if component in {"asr", "embedding"} else component
        return {"requested_component": component, "managed_component": managed, "recovered": True}


def result(component, status="ready"):
    return ProbeResult(component=component, status=status, latency_ms=1, checked_at=datetime.now(timezone.utc), logical_id=component, error=None if status == "ready" else "down")


def app(launcher, statuses=None):
    registry = ModelRegistry(ROOT)
    statuses = statuses or {}
    probes = FunctionalProbeRunner(ROOT, injected={name: (lambda n=name: result(n, statuses.get(n, "ready"))) for name in ("llm", "asr", "tts", "avatar", "embedding")})
    return TestClient(ApiGateway(registry, HealthAggregator(registry, probes), launcher_service=launcher).build_app())


def test_launcher_service_maps_speech_components_and_windows_path():
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs)); return SimpleNamespace(returncode=0, stdout="{}", stderr="")
    service = LauncherService(ROOT, runner=runner)
    response = service.recover("embedding")
    assert response["managed_component"] == "speech"
    assert calls[0][0][-1] == "speech"
    assert calls[0][0][5].startswith("C:\\")
    tts_response = service.recover("tts")
    assert tts_response["managed_component"] == "gateway"
    assert calls[1][0][-1] == "gateway"


def test_recover_all_runs_real_probe_contract_for_five_components():
    launcher = FakeLauncher()
    client = app(launcher)
    response = client.post("/api/v1/launcher/recover", json={"component": "all"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert set(body["probes"]) == {"llm", "asr", "tts", "avatar", "embedding"}
    assert launcher.calls == ["all"]


def test_recover_failure_never_reports_ready():
    client = app(FakeLauncher(fail=True))
    assert client.post("/api/v1/launcher/recover", json={"component": "all"}).status_code == 503
