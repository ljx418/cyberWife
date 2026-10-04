from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway


class _Registry:
    def all_components(self):
        return []


class _Aggregator:
    supports_functional_probes = False

    def snapshot(self):
        return {"status": "ready"}


def test_release_frontend_is_served_without_shadowing_api(tmp_path: Path):
    (tmp_path / "index.html").write_text("<title>cyberWife release</title>", encoding="utf-8")
    app = ApiGateway(_Registry(), _Aggregator(), static_root=tmp_path).build_app()

    with TestClient(app) as client:
        root = client.get("/")
        health = client.get("/api/v1/health")

    assert root.status_code == 200
    assert "cyberWife release" in root.text
    assert health.status_code == 200
    assert health.json() == {"status": "ready"}


def test_missing_release_frontend_fails_explicitly(tmp_path: Path):
    app = ApiGateway(_Registry(), _Aggregator(), static_root=tmp_path).build_app()
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 503
    assert response.json()["code"] == "health.component_unavailable"
