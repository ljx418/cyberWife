from __future__ import annotations

import json
import struct
from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.memory_service import MemoryService
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.output_sanitizer import OutputSanitizer
from cyberwife.application.prompt_compiler import PromptCompiler
from cyberwife.application.turn_pipeline import TurnPipeline
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


class _Speech:
    def transcribe(self, _pcm, _sample_rate):
        return {"speech_detected": True, "text": "我喜欢紫色风筝", "confidence": .99, "language": "zh"}


class _Llm:
    def generate_stream(self, _prompt, **_kwargs):
        yield "好的，我记住了。"


class _Embedding:
    def embed(self, _text):
        return [1.0] + [0.0] * 511

    def embed_batch(self, texts):
        return [self.embed(text) for text in texts]


def _stack(tmp_path):
    root = Path(__file__).resolve().parents[3]
    repo = SqliteRepository(tmp_path / "no-record.db", root / "migrations" / "0001_init.sql")
    memories = SqliteMemoryRepository(repo.conn, repo.lock)
    memory_service = MemoryService(repo, memories, _Embedding())
    registry = ModelRegistry(root)
    orchestrator = ConversationOrchestrator()
    pipeline = TurnPipeline(
        orchestrator, _Speech(), _Llm(), PromptCompiler(), OutputSanitizer(),
        repository=repo, memory_provider=memory_service.prompt_memories,
    )
    gateway = ApiGateway(
        registry, HealthAggregator(registry), repository=repo, orchestrator=orchestrator,
        turn_pipeline=pipeline, memory_service=memory_service,
    )
    return TestClient(gateway.build_app()), repo, orchestrator


def _one_turn(ws):
    initial = ws.receive_json()
    ws.send_bytes(struct.pack("<IH", 1, 0) + b"\x01\x00" * 320)
    ws.send_json({"type": "audio.silence", "turn_id": 1, "event_seq": 1})
    events = [initial]
    while True:
        event = ws.receive_json()
        events.append(event)
        if event["type"] == "state.changed" and event["payload"].get("current") == "listening":
            break
    return events


def test_no_record_session_uses_opaque_ref_and_writes_no_business_rows(tmp_path):
    client, repo, orchestrator = _stack(tmp_path)
    created = client.post("/api/v1/sessions", json={"recording_policy": "none"})
    assert created.status_code == 200
    payload = created.json()
    assert payload["id"] == "0"
    assert len(payload["session_ref"]) == 32 and not payload["session_ref"].isdecimal()
    internal_id = orchestrator.list_sessions()[0].id
    assert str(internal_id) not in json.dumps(payload)
    with client.websocket_connect(payload["ws_url"]) as ws:
        events = _one_turn(ws)
        ws.send_json({"type": "conversation.stop", "event_seq": 2})
    serialized = json.dumps(events, ensure_ascii=False)
    assert str(internal_id) not in serialized
    assert all(event.get("session_id") in (None, "0") for event in events)
    for table in ("sessions", "turns", "session_transcripts", "session_summaries", "memories"):
        assert repo.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert repo.conn.execute("SELECT COUNT(*) FROM memory_vectors_meta").fetchone()[0] == 0


def test_mid_session_switch_purges_data_and_invalidates_numeric_ref(tmp_path):
    client, repo, _ = _stack(tmp_path)
    created = client.post("/api/v1/sessions", json={"recording_policy": "standard"}).json()
    session_id = int(created["id"])
    with client.websocket_connect(created["ws_url"]) as ws:
        _one_turn(ws)
    # Complete memory extraction just as a real ended/managed session would.
    # The switch must erase the turn and every derived memory layer.
    response = client.patch(f"/api/v1/sessions/{session_id}/no_record")
    assert response.status_code == 200
    switched = response.json()
    assert switched["id"] == "0" and switched["deleted"]["wal_checkpoint_busy"] == 0
    assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 404
    assert repo.conn.execute("SELECT COUNT(*) FROM sessions WHERE id=?", (session_id,)).fetchone()[0] == 0
    assert repo.conn.execute("SELECT COUNT(*) FROM turns WHERE session_id=?", (session_id,)).fetchone()[0] == 0
    assert client.delete(f"/api/v1/sessions/{switched['session_ref']}").status_code == 200


def test_ephemeral_id_does_not_advance_standard_session_sequence(tmp_path):
    client, _, _ = _stack(tmp_path)
    hidden = client.post("/api/v1/sessions", json={"recording_policy": "none"}).json()
    standard = client.post("/api/v1/sessions", json={"recording_policy": "standard"}).json()
    assert hidden["id"] == "0"
    assert standard["id"] == "1"
