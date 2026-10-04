"""M1-03 unit test: domain 层状态机 + 不变量。"""
import pytest
from datetime import datetime, timezone

from cyberwife.domain.conversation import (
    Session,
    SessionState,
    Turn,
    RecordingPolicy,
    is_legal_transition,
)
from cyberwife.domain.profile import (
    Profile,
    Consent,
    ConsentScope,
    AssetVersion,
    AssetKind,
    AssetStatus,
)
from cyberwife.domain.memory import (
    MemoryRecord,
    MemoryWithVector,
    OnboardingDraft,
)


class TestStateMachine:
    def test_legal_transitions(self):
        assert is_legal_transition(SessionState.IDLE, SessionState.LISTENING)
        assert is_legal_transition(SessionState.SPEAKING, SessionState.INTERRUPTED)
        assert is_legal_transition(SessionState.ERROR, SessionState.LISTENING)

    def test_illegal_transitions(self):
        # speaking → thinking（不保存中间 turn，非法）
        assert not is_legal_transition(SessionState.SPEAKING, SessionState.THINKING)
        # idle → thinking（无中间状态）
        assert not is_legal_transition(SessionState.IDLE, SessionState.THINKING)
        # interrupted → thinking（必须先回 listening）
        assert not is_legal_transition(SessionState.INTERRUPTED, SessionState.THINKING)
        # interrupted → speaking（直接跳到 speaking 不允许）
        assert not is_legal_transition(SessionState.INTERRUPTED, SessionState.SPEAKING)
        # listening → speaking（必须经过 thinking）
        assert not is_legal_transition(SessionState.LISTENING, SessionState.SPEAKING)

    def test_error_recovers_to_any(self):
        # error → 任意非 idle/error 状态允许（recovery 路径）
        for s in [SessionState.LISTENING, SessionState.THINKING, SessionState.SPEAKING, SessionState.INTERRUPTED, SessionState.IDLE]:
            assert is_legal_transition(SessionState.ERROR, s), f"error → {s} should be legal"

    def test_self_loop_allowed(self):
        assert is_legal_transition(SessionState.LISTENING, SessionState.LISTENING)

    def test_session_transition_enforces_legality(self):
        s = Session(id=1)
        with pytest.raises(ValueError, match="illegal state transition"):
            s.transition(SessionState.THINKING)  # idle → thinking 非法

    def test_event_seq_monotonic(self):
        s = Session(id=1)
        assert s.next_event_seq() == 1
        assert s.next_event_seq() == 2
        assert s.next_event_seq() == 3

    def test_late_event_detection(self):
        s = Session(id=1, active_turn=Turn(id=5, session_id=1, ordinal=0))
        # event_seq 已到 10，新 event_seq=5 视为迟到
        s.last_event_seq = 10
        assert s.is_late_event(event_seq=5, turn_id=None)
        # turn_id < active_turn.id 也视为迟到
        assert s.is_late_event(event_seq=20, turn_id=3)
        # event_seq 更大且 turn_id >= active 视为不迟到
        assert not s.is_late_event(event_seq=11, turn_id=6)


class TestProfileConsent:
    def test_consent_revoke(self):
        c = Consent(id=1, scope=ConsentScope.ALL, policy_version="v1", granted=True)
        c.revoke()
        assert not c.granted
        assert c.revoked_at is not None

    def test_profile_bump_version(self):
        p = Profile(id=1, name="A", user_nickname="B", version=0)
        p.bump_version()
        assert p.version == 1
        p.bump_version()
        assert p.version == 2


class TestMemory:
    def test_memory_with_vector_dim_check(self):
        m = MemoryRecord(id=1, content="test", confidence=0.9)
        emb_512 = [0.0] * 512
        mv = MemoryWithVector(memory=m, embedding=emb_512)
        assert len(mv.embedding) == 512

    def test_memory_with_vector_wrong_dim(self):
        m = MemoryRecord(id=1, content="test", confidence=0.9)
        with pytest.raises(ValueError, match="dim must be 512"):
            MemoryWithVector(memory=m, embedding=[0.0] * 511)

    def test_onboarding_bump_step(self):
        d = OnboardingDraft()
        d.bump_step(2)
        assert d.step_completed == 2
        d.bump_step(1)  # 回退忽略
        assert d.step_completed == 2
        with pytest.raises(ValueError, match="step_completed must be in"):
            d.bump_step(5)
