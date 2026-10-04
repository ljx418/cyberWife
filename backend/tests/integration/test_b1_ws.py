import struct
import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.output_sanitizer import OutputSanitizer
from cyberwife.application.prompt_compiler import PromptCompiler
from cyberwife.application.turn_pipeline import TurnPipeline
from cyberwife.application.media_pipeline import MediaPipeline
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


class _Speech:
    def transcribe(self, pcm, sample_rate):
        assert len(pcm) == 640
        return {
            "speech_detected": True,
            "text": "你好",
            "confidence": 0.99,
            "language": "zh",
            "segments": [{"start_ms": 0, "end_ms": 20, "text": "你好", "confidence": 0.99}],
        }


class _Llm:
    def generate_stream(self, prompt, **kwargs):
        yield "你好，"
        yield "我在。"


class _Tts:
    last_metrics = {}

    def synthesize_stream(self, text, *_args):
        assert text
        yield b"\x01\x00" * 320


def _client(tmp_path):
    root = Path(__file__).resolve().parents[3]
    repo = SqliteRepository(tmp_path / "b1.db", root / "migrations" / "0001_init.sql")
    registry = ModelRegistry(root)
    orchestrator = ConversationOrchestrator()
    pipeline = TurnPipeline(
        orchestrator,
        _Speech(),
        _Llm(),
        PromptCompiler(),
        OutputSanitizer(),
        repository=repo,
        media_pipeline=MediaPipeline(_Tts()),
        voice_reference_provider=lambda: ("ref.wav", "参考"),
    )
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        repository=repo,
        orchestrator=orchestrator,
        turn_pipeline=pipeline,
    ).build_app()
    return TestClient(app), repo


def test_session_ws_binary_to_final_text(tmp_path):
    client, repo = _client(tmp_path)
    created = client.post("/api/v1/sessions", json={"recording_policy": "standard"})
    assert created.status_code == 200
    session_id = int(created.json()["id"])
    with client.websocket_connect(f"/ws/v1/sessions/{session_id}") as ws:
        assert ws.receive_json()["type"] == "state.changed"
        ws.send_bytes(struct.pack("<IH", 1, 0) + b"\x01\x00" * 320)
        ws.send_json({"type": "audio.silence", "turn_id": 1, "event_seq": 1})
        received = []
        while True:
            event = ws.receive_json()
            received.append(event)
            if event["type"] == "reply.audio.complete":
                ws.send_json({
                    "type": "audio.playback.ended",
                    "turn_id": event["turn_id"],
                    "generation": event["payload"]["generation"],
                })
            if event["type"] == "state.changed" and event["payload"]["current"] == "listening":
                break
    types = [event["type"] for event in received]
    assert "transcript.final" in types
    assert "reply.text.delta" in types
    assert "reply.text.final" in types
    assert len({event["turn_id"] for event in received if event["turn_id"] is not None}) == 1
    root = Path(__file__).resolve().parents[3]
    envelope_schema = json.loads((root / "schemas/ws/envelope.schema.json").read_text())
    payload_schemas = {
        "state.changed": "state.changed.schema.json",
        "transcript.final": "transcript.schema.json",
        "reply.text.delta": "reply.schema.json",
        "reply.text.final": "reply.schema.json",
    }
    for event in received:
        jsonschema.validate(event, envelope_schema)
        if event["type"] in payload_schemas:
            schema = json.loads((root / "schemas/ws" / payload_schemas[event["type"]]).read_text())
            jsonschema.validate(event["payload"], schema)
    row = repo.conn.execute("SELECT user_text, assistant_text, status FROM turns").fetchone()
    assert tuple(row) == ("你好", "你好，我在。", "completed")


def test_ws_rejects_wrong_size_and_cross_turn(tmp_path):
    client, _ = _client(tmp_path)
    session_id = int(client.post("/api/v1/sessions", json={}).json()["id"])
    with client.websocket_connect(f"/ws/v1/sessions/{session_id}") as ws:
        ws.receive_json()
        ws.send_bytes(b"bad")
        assert ws.receive_json()["payload"]["code"] == "frame.size_limit"
        ws.send_bytes(struct.pack("<IH", 2, 0) + b"\0" * 640)
        assert ws.receive_json()["payload"]["code"] == "turn.late_event"


def test_session_delete_is_idempotent_contract(tmp_path):
    client, _ = _client(tmp_path)
    session_id = int(client.post("/api/v1/sessions", json={}).json()["id"])
    assert client.delete(f"/api/v1/sessions/{session_id}").status_code == 200
    assert client.delete(f"/api/v1/sessions/{session_id + 999}").status_code == 404


def test_ws_accepts_matching_playback_confirmation_and_rejects_duplicate(tmp_path):
    client, _ = _client(tmp_path)
    session_id = int(client.post("/api/v1/sessions", json={}).json()["id"])
    with client.websocket_connect(f"/ws/v1/sessions/{session_id}") as ws:
        ws.receive_json()
        ws.send_bytes(struct.pack("<IH", 1, 0) + b"\x01\x00" * 320)
        ws.send_json({"type": "audio.silence", "turn_id": 1, "event_seq": 1})
        trace_id = None
        generation = None
        while True:
            event = ws.receive_json()
            if event["type"] == "transcript.final":
                trace_id = event["payload"]["trace_id"]
                generation = event["payload"]["generation"]
            if event["type"] == "reply.audio.complete":
                ws.send_json({
                    "type": "audio.playback.ended",
                    "turn_id": event["turn_id"],
                    "generation": event["payload"]["generation"],
                })
            if event["type"] == "state.changed" and event["payload"]["current"] == "listening":
                break
        assert trace_id and generation == 1
        confirmation = {
            "type": "audio.playback.started",
            "turn_id": 1,
            "trace_id": trace_id,
            "generation": generation,
            "asr_to_playback_ms": 321.5,
            "browser_first_non_silent_wall_ms": 123456.0,
            "event_seq": 2,
        }
        ws.send_json(confirmation)
        ws.send_json({**confirmation, "event_seq": 3})
        duplicate_error = ws.receive_json()
        assert duplicate_error["payload"]["code"] == "turn.late_event"

    latency = client.get("/api/v1/runtime/metrics").json()["latency"]
    assert latency["buckets"]["normal"]["complete_count"] == 1
    assert latency["buckets"]["normal"]["p50_ms"] == 321.5
