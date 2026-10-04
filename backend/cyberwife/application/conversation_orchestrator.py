"""ConversationOrchestrator — M3-03 六态状态机 + WS envelope + event_seq 单调。

按 implementation-contracts §5/§6/§18 与 prototype-spec §6 6×6 矩阵。
按 user 2026-09-23 决策：M3 仅做 Orchestrator 状态机骨架，真实 ASR/LLM/TTS 接入留 M3-stretch。

实现要点：
- session_id 单调递增 turn_id、event_seq
- 迟到事件（event_seq ≤ seen 或 turn_id < active）丢弃
- WS envelope 6 字段：type, session_id, turn_id, event_seq, occurred_at, payload
"""
from __future__ import annotations

import secrets
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Optional

from cyberwife.domain.conversation import RecordingPolicy, Session, SessionState, Turn


def gen_trace_id() -> str:
    """ULID 风格 trace_id（26 字符 Crockford base32；§4）。"""
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    raw = secrets.token_bytes(32)
    return "".join(alphabet[b % 32] for b in raw)[:26]


def gen_ulid_timestamp() -> str:
    """ISO8601 时间戳；§4 ULID 也可拼时间前缀，这里简化为 date-time 字符串。"""
    return datetime.now(timezone.utc).isoformat()


class Event:
    """WS 事件 envelope。"""

    __slots__ = ("type", "session_id", "turn_id", "event_seq", "occurred_at", "payload")

    def __init__(
        self,
        type_: str,
        session_id: int | str,
        turn_id: Optional[int],
        event_seq: int,
        payload: Optional[dict] = None,
    ) -> None:
        self.type = type_
        self.session_id = session_id
        self.turn_id = turn_id
        self.event_seq = event_seq
        self.occurred_at = gen_ulid_timestamp()
        self.payload = payload or {}

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "session_id": str(self.session_id),
            "turn_id": self.turn_id,
            "event_seq": self.event_seq,
            "occurred_at": self.occurred_at,
            "payload": self.payload,
        }


class ConversationOrchestrator:
    """六态会话编排器；持有 Session 状态 + event_seq 单调。"""

    def __init__(self) -> None:
        self._sessions: dict[int, Session] = {}
        self._next_session_id: int = 1
        self._next_turn_id: dict[int, int] = {}
        self._generation: dict[int, int] = {}
        self._public_session_ids: dict[int, int | str] = {}
        self._next_ephemeral_session_id: int = 2**62

    def open_session(
        self,
        recording_policy: str = "standard",
        *,
        session_id: int | None = None,
        public_session_id: str | None = None,
    ) -> Session:
        """新建一个会话（FR-08）；初始状态 idle。"""
        try:
            rp = RecordingPolicy(recording_policy)
        except ValueError:
            rp = RecordingPolicy.STANDARD
        if session_id is not None:
            sid = session_id
        elif rp == RecordingPolicy.NONE:
            sid = self._next_ephemeral_session_id
            self._next_ephemeral_session_id += 1
        else:
            sid = self._next_session_id
        if sid in self._sessions:
            raise ValueError(f"session already exists: {sid}")
        # Ephemeral no-record identifiers live in a disjoint, process-local
        # namespace.  They must never advance or otherwise contaminate the
        # durable session id sequence.
        if rp != RecordingPolicy.NONE:
            self._next_session_id = max(self._next_session_id, sid + 1)
        s = Session(id=sid, recording_policy=rp)
        self._sessions[sid] = s
        self._next_turn_id[sid] = 1
        self._generation[sid] = 0
        self._public_session_ids[sid] = public_session_id or ("0" if rp == RecordingPolicy.NONE else sid)
        return s

    def public_session_id(self, session_id: int) -> int | str:
        return self._public_session_ids.get(session_id, "0")

    def enable_no_record(self, session_id: int) -> None:
        session = self._sessions[session_id]
        session.recording_policy = RecordingPolicy.NONE
        self._public_session_ids[session_id] = "0"

    def drop_session(self, session_id: int) -> None:
        self._sessions.pop(session_id, None)
        self._next_turn_id.pop(session_id, None)
        self._generation.pop(session_id, None)
        self._public_session_ids.pop(session_id, None)

    def begin_turn(self, session_id: int, expected_turn_id: int) -> Turn:
        """Create exactly one active turn after an ASR final."""
        s = self._sessions.get(session_id)
        if s is None:
            raise KeyError(session_id)
        if s.state != SessionState.LISTENING:
            raise ValueError(f"session is not listening: {s.state.value}")
        next_id = self._next_turn_id[session_id]
        if expected_turn_id != next_id:
            raise ValueError(f"turn id mismatch: expected {next_id}, got {expected_turn_id}")
        if s.active_turn is not None and not s.active_turn.is_terminal():
            raise ValueError("session already has an active turn")
        turn = Turn(id=next_id, session_id=session_id, ordinal=next_id)
        s.active_turn = turn
        self._next_turn_id[session_id] = next_id + 1
        self._generation[session_id] += 1
        return turn

    def complete_turn(self, session_id: int, assistant_text: str) -> Turn:
        s = self._sessions.get(session_id)
        if s is None or s.active_turn is None:
            raise KeyError(session_id)
        s.active_turn.assistant_text = assistant_text
        s.active_turn.status = "completed"
        return s.active_turn

    def next_turn_id(self, session_id: int) -> int:
        if session_id not in self._next_turn_id:
            raise KeyError(session_id)
        return self._next_turn_id[session_id]

    def generation(self, session_id: int) -> int:
        return self._generation.get(session_id, 0)

    def invalidate_generation(self, session_id: int) -> int:
        """Atomically make every event from the current generation stale."""
        if session_id not in self._generation:
            raise KeyError(session_id)
        self._generation[session_id] += 1
        return self._generation[session_id]

    def cancel_active_turn(self, session_id: int) -> bool:
        session = self._sessions.get(session_id)
        if session is None or session.active_turn is None:
            return False
        if session.active_turn.status == "cancelled":
            return False
        # A turn becomes "completed" once its text is persisted, while its
        # audio can still be playing.  A barge-in during SPEAKING must retain
        # the stronger user-visible outcome: the turn was cancelled.
        session.active_turn.status = "cancelled"
        return True

    def close_session(self, session_id: int) -> bool:
        s = self._sessions.get(session_id)
        if s is None:
            return False
        if s.active_turn is not None and not s.active_turn.is_terminal():
            s.active_turn.status = "cancelled"
        s.ended_at = datetime.now(timezone.utc)
        if s.state != SessionState.IDLE:
            try:
                s.transition(SessionState.IDLE)
            except ValueError:
                s.state = SessionState.IDLE
        return True

    def get(self, session_id: int) -> Optional[Session]:
        return self._sessions.get(session_id)

    def emit(
        self,
        session_id: int,
        type_: str,
        *,
        turn_id: Optional[int] = None,
        payload: Optional[dict] = None,
    ) -> Optional[Event]:
        """分配 event_seq + 构造 Event。"""
        s = self._sessions.get(session_id)
        if s is None:
            return None
        seq = s.next_event_seq()
        return Event(type_, self.public_session_id(session_id), turn_id, seq, payload)

    def emit_stream(
        self,
        session_id: int,
        type_: str,
        *,
        turn_id: Optional[int] = None,
        payload_factory=None,
    ) -> Iterator[Event]:
        """流式 yield 多事件（M3-04 LLM delta 用）。"""
        s = self._sessions.get(session_id)
        if s is None:
            return
        idx = 0
        while True:
            seq = s.next_event_seq()
            payload = payload_factory(idx) if payload_factory else {}
            yield Event(type_, self.public_session_id(session_id), turn_id, seq, payload)
            idx += 1
            # 外部代码通过 close() 或 sentinel 退出
            break  # 单次；多次由调用方控制

    def is_late(self, session_id: int, event_seq: int, turn_id: Optional[int]) -> bool:
        s = self._sessions.get(session_id)
        if s is None:
            return True
        return s.is_late_event(event_seq, turn_id)

    def transition(self, session_id: int, new_state: SessionState) -> bool:
        """状态转换；非法边返回 False（不抛异常，便于上游 retry）。"""
        s = self._sessions.get(session_id)
        if s is None:
            return False
        try:
            s.transition(new_state)
            return True
        except ValueError:
            return False

    def list_sessions(self) -> list[Session]:
        return list(self._sessions.values())
