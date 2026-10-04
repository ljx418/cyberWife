"""M3-03 Orchestrator + WS envelope 单元测试。"""
import pytest

from cyberwife.application.conversation_orchestrator import (
    ConversationOrchestrator,
    Event,
    gen_trace_id,
)
from cyberwife.domain.conversation import SessionState


class TestOrchestrator:
    def test_open_session_returns_idle(self):
        o = ConversationOrchestrator()
        s = o.open_session()
        assert s.id == 1
        assert s.state == SessionState.IDLE
        assert s.recording_policy.value == "standard"

    def test_open_session_recording_none(self):
        o = ConversationOrchestrator()
        s = o.open_session("none")
        assert s.recording_policy.value == "none"

    def test_open_session_invalid_falls_back(self):
        o = ConversationOrchestrator()
        s = o.open_session("invalid_value")
        assert s.recording_policy.value == "standard"

    def test_emit_event_seq_monotonic(self):
        o = ConversationOrchestrator()
        s = o.open_session()
        e1 = o.emit(s.id, "state.changed", payload={"from": "idle", "to": "listening"})
        e2 = o.emit(s.id, "transcript.partial", payload={"text": "你"})
        e3 = o.emit(s.id, "transcript.final", payload={"text": "你好"})
        assert e1.event_seq == 1
        assert e2.event_seq == 2
        assert e3.event_seq == 3
        # envelope 6 字段
        for e in (e1, e2, e3):
            assert e.type
            assert e.session_id == s.id
            assert e.event_seq >= 1
            assert e.occurred_at  # ISO timestamp
            assert "payload" in e.to_dict()

    def test_is_late_event_detection(self):
        o = ConversationOrchestrator()
        s = o.open_session()
        o.emit(s.id, "x")  # seq=1
        o.emit(s.id, "y")  # seq=2
        # event_seq ≤ 2 视为迟到
        assert o.is_late(s.id, 1, None)
        assert o.is_late(s.id, 2, None)
        assert not o.is_late(s.id, 3, None)

    def test_transition_legal(self):
        o = ConversationOrchestrator()
        s = o.open_session()
        assert o.transition(s.id, SessionState.LISTENING) is True
        assert o.get(s.id).state == SessionState.LISTENING

    def test_transition_illegal_returns_false(self):
        o = ConversationOrchestrator()
        s = o.open_session()
        # idle → thinking 非法
        assert o.transition(s.id, SessionState.THINKING) is False
        assert o.get(s.id).state == SessionState.IDLE

    def test_emit_unknown_session_returns_none(self):
        o = ConversationOrchestrator()
        assert o.emit(999, "x") is None

    def test_multiple_sessions_independent(self):
        o = ConversationOrchestrator()
        s1 = o.open_session()
        s2 = o.open_session()
        o.emit(s1.id, "x")
        o.emit(s2.id, "y")
        assert o.get(s1.id).last_event_seq == 1
        assert o.get(s2.id).last_event_seq == 1


class TestUlidHelpers:
    def test_trace_id_format(self):
        tid = gen_trace_id()
        assert len(tid) == 26
        assert all(c in "0123456789ABCDEFGHJKMNPQRSTVWXYZ" for c in tid)

    def test_trace_id_unique(self):
        ids = {gen_trace_id() for _ in range(100)}
        assert len(ids) == 100


class TestEventEnvelope:
    def test_envelope_6_fields(self):
        e = Event("test", session_id=1, turn_id=5, event_seq=10, payload={"k": "v"})
        d = e.to_dict()
        # §6 envelope 6 字段
        assert d["type"] == "test"
        assert d["session_id"] == "1"
        assert d["turn_id"] == 5
        assert d["event_seq"] == 10
        assert d["occurred_at"]
        assert d["payload"] == {"k": "v"}

    def test_envelope_optional_turn_id_none(self):
        e = Event("system.event", session_id=1, turn_id=None, event_seq=1)
        d = e.to_dict()
        assert d["turn_id"] is None
