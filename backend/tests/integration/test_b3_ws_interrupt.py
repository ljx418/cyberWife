import struct
import time
from pathlib import Path

from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.application.output_sanitizer import OutputSanitizer
from cyberwife.application.prompt_compiler import PromptCompiler
from cyberwife.application.turn_pipeline import TurnPipeline
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


class _Speech:
    def transcribe(self, pcm, sample_rate):
        return {
            "speech_detected": True,
            "text": "请讲一个很长的故事",
            "confidence": 0.99,
            "language": "zh",
            "segments": [{"start_ms": 0, "end_ms": 20, "text": "请讲一个很长的故事", "confidence": 0.99}],
        }


class _SlowLlm:
    def __init__(self):
        self.cancelled = False

    def generate_stream(self, prompt, **kwargs):
        for _ in range(200):
            if self.cancelled:
                return
            time.sleep(0.005)
            yield "这是仍在生成的长回答。"

    def cancel(self, request_id):
        self.cancelled = True
        return True


def test_ws_receiver_accepts_barge_in_while_turn_is_running(tmp_path):
    root = Path(__file__).resolve().parents[3]
    repo = SqliteRepository(tmp_path / "b3.db", root / "migrations" / "0001_init.sql")
    registry = ModelRegistry(root)
    orchestrator = ConversationOrchestrator()
    llm = _SlowLlm()
    pipeline = TurnPipeline(
        orchestrator,
        _Speech(),
        llm,
        PromptCompiler(),
        OutputSanitizer(),
        repository=repo,
    )
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        repository=repo,
        orchestrator=orchestrator,
        turn_pipeline=pipeline,
    ).build_app()

    with TestClient(app).websocket_connect("/ws/v1/sessions/999") as missing:
        assert missing.receive_json()["type"] == "error"

    client = TestClient(app)
    session_id = int(client.post("/api/v1/sessions", json={}).json()["id"])
    with client.websocket_connect(f"/ws/v1/sessions/{session_id}") as ws:
        ws.receive_json()
        ws.send_bytes(struct.pack("<IH", 1, 0) + b"\x01\x00" * 320)
        ws.send_json({"type": "audio.silence", "turn_id": 1, "event_seq": 1})
        while True:
            event = ws.receive_json()
            if event["type"] == "state.changed" and event["payload"].get("current") == "thinking":
                break

        # The utterance that causes barge-in may already be arriving while the
        # old turn speaks. It must survive cancellation and become turn 2.
        ws.send_bytes(struct.pack("<IH", 2, 0) + b"\x01\x00" * 320)
        started = time.perf_counter()
        ws.send_json({"type": "barge_in.detected", "turn_id": 1, "event_seq": 2})
        observed = []
        while len(observed) < 8:
            event = ws.receive_json()
            observed.append(event)
            if event["type"] == "turn.cancelled":
                break

        assert (time.perf_counter() - started) < 0.4
        assert any(event["type"] == "barge_in.detected" for event in observed)
        assert observed[-1]["type"] == "turn.cancelled"
        assert observed[-1]["payload"]["next_state"] == "listening"
        cancelled_generation = observed[-1]["payload"]["cancelled_generation"]

        ws.send_json({"type": "audio.silence", "turn_id": 2, "event_seq": 3})
        # A delayed/repeated cancel for turn 1 must never cancel the newly
        # registered turn 2.
        ws.send_json({"type": "barge_in.detected", "turn_id": 1, "event_seq": 4})
        for _ in range(20):
            event = ws.receive_json()
            assert not (event["type"] == "turn.cancelled" and event["turn_id"] == 2)
            assert not (
                event["type"].startswith("reply.")
                and event["payload"].get("generation") == cancelled_generation
            )
            if event["type"] == "transcript.final" and event["turn_id"] == 2:
                break

    cancelled = repo.conn.execute(
        "SELECT status FROM turns WHERE session_id=? AND ordinal=1", (session_id,)
    ).fetchone()
    assert tuple(cancelled) == ("cancelled",)
