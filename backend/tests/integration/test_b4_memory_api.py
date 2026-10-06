from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry


class _MemoryService:
    def __init__(self):
        self.items = {1: {"id": 1, "content": "用户喜欢红茶", "edited": False}}

    def list_or_search(self, query=""):
        return list(self.items.values())

    def create_manual(self, content):
        if not str(content).strip():
            raise ValueError("memory_content_invalid")
        next_id = max(self.items, default=0) + 1
        self.items[next_id] = {"id": next_id, "content": content, "edited": True, "source": "manual"}
        return self.items[next_id]

    def all_candidates(self):
        return [{"session_id": 8, "turn_id": 2, "content": "今天想散步", "reason": "temporary_context"}]

    def confirm_candidate(self, *, session_id, turn_id, content):
        if (session_id, turn_id, content) != (8, 2, "今天想散步"):
            return None
        return self.create_manual(content)

    def reject_candidate(self, *, session_id, turn_id, content):
        return (session_id, turn_id, content) == (8, 2, "今天想散步")

    def edit(self, memory_id, content):
        if memory_id not in self.items:
            return None
        self.items[memory_id] = {"id": memory_id, "content": content, "edited": True}
        return self.items[memory_id]

    def delete(self, memory_id):
        return self.items.pop(memory_id, None) is not None

    def purge_all(self):
        count = len(self.items)
        self.items.clear()
        return count


def make_client():
    root = Path(__file__).resolve().parents[3]
    registry = ModelRegistry(root)
    service = _MemoryService()
    gateway = ApiGateway(registry, HealthAggregator(registry), memory_service=service)
    return TestClient(gateway.build_app()), service


def test_memory_crud_and_purge_confirmation_contract():
    client, service = make_client()
    assert client.get("/api/v1/memories?q=红茶").json()["items"][0]["id"] == 1
    edited = client.patch("/api/v1/memories/1", json={"content": "用户喜欢绿茶"})
    assert edited.status_code == 200
    assert edited.json()["edited"] is True
    assert client.request("DELETE", "/api/v1/memories", json={}).status_code == 412
    purged = client.request("DELETE", "/api/v1/memories", json={"confirmation": "PURGE_ALL"})
    assert purged.status_code == 200
    assert purged.json()["deleted"] == 1
    assert service.items == {}


def test_manual_and_candidate_api_contracts():
    client, _ = make_client()
    created = client.post("/api/v1/memories", json={"content": "用户喜欢安静的房间"})
    assert created.status_code == 201
    assert created.json()["source"] == "manual"
    candidates = client.get("/api/v1/memory-candidates")
    assert candidates.status_code == 200
    assert candidates.json()["items"][0]["content"] == "今天想散步"
    confirmed = client.post(
        "/api/v1/memory-candidates/confirm",
        json={"session_id": 8, "turn_id": 2, "content": "今天想散步"},
    )
    assert confirmed.status_code == 200
    rejected = client.post(
        "/api/v1/memory-candidates/reject",
        json={"session_id": 8, "turn_id": 2, "content": "今天想散步"},
    )
    assert rejected.status_code == 200


def test_candidate_confirmation_validates_identity_and_manual_content():
    client, _ = make_client()
    assert client.post("/api/v1/memories", json={"content": ""}).status_code == 422
    missing = client.post(
        "/api/v1/memory-candidates/confirm",
        json={"session_id": 9, "turn_id": 2, "content": "今天想散步"},
    )
    assert missing.status_code == 404


def test_missing_memory_uses_catalogued_error():
    client, _ = make_client()
    response = client.delete("/api/v1/memories/99")
    assert response.status_code == 404
    assert response.json()["code"] == "memory.not_found"
