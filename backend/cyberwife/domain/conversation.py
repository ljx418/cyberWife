"""对话域：Session / Turn / 状态机。

按 prototype-spec §6 6×6 状态转换矩阵与 implementation-contracts §19 事件归属。

不变量：
- 每 session 最多一个 active turn
- 旧 turn 事件（turn_id < active 或 event_seq ≤ seen）丢弃
- 状态机严格走 §5 合法边
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SessionState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class RecordingPolicy(str, Enum):
    STANDARD = "standard"  # FR-08 标准记录：会话转录 30 天 + 长期记忆
    NONE = "none"          # FR-13 本次不记录：转录/摘要/向量均不写入


# 6×6 合法转换矩阵（prototype-spec §6）
_LEGAL_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.IDLE:        {SessionState.LISTENING, SessionState.ERROR},
    SessionState.LISTENING:   {SessionState.THINKING, SessionState.IDLE, SessionState.ERROR},
    SessionState.THINKING:    {SessionState.SPEAKING, SessionState.INTERRUPTED, SessionState.ERROR, SessionState.IDLE},
    SessionState.SPEAKING:    {SessionState.INTERRUPTED, SessionState.LISTENING, SessionState.IDLE, SessionState.ERROR},
    SessionState.INTERRUPTED: {SessionState.LISTENING, SessionState.ERROR},
    SessionState.ERROR:        {SessionState.IDLE, SessionState.LISTENING, SessionState.THINKING, SessionState.SPEAKING, SessionState.INTERRUPTED},
}


def is_legal_transition(prev: SessionState, current: SessionState) -> bool:
    """返回 prev → current 是否为合法转换（含自环）。"""
    if prev == current:
        return True
    return current in _LEGAL_TRANSITIONS.get(prev, set())


@dataclass
class Turn:
    """一轮对话：用户一句话 + 助手一句话 + 状态。"""

    id: int
    session_id: int
    ordinal: int
    user_text: str = ""
    assistant_text: str = ""
    status: str = "pending"  # pending | streaming | completed | cancelled
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def is_terminal(self) -> bool:
        return self.status in {"completed", "cancelled"}


@dataclass
class Session:
    """一个对话会话；FR-08/FR-13。"""

    id: int
    recording_policy: RecordingPolicy = RecordingPolicy.STANDARD
    state: SessionState = SessionState.IDLE
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # FR-14 = ended_at + 30d UTC
    active_turn: Optional[Turn] = None
    last_event_seq: int = 0  # 单调递增；迟到事件丢弃

    def transition(self, new_state: SessionState) -> None:
        """状态机转换；非法边抛 ValueError。"""
        if not is_legal_transition(self.state, new_state):
            raise ValueError(
                f"illegal state transition: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state

    def next_event_seq(self) -> int:
        """分配下一个单调 event_seq。"""
        self.last_event_seq += 1
        return self.last_event_seq

    def is_late_event(self, event_seq: int, turn_id: Optional[int]) -> bool:
        """判定一个事件是否迟到（应被前端丢弃）。"""
        if event_seq <= self.last_event_seq:
            return True
        if turn_id is not None and self.active_turn is not None and turn_id < self.active_turn.id:
            return True
        return False
