"""Turn cancellation primitives shared by the realtime pipeline."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone


_REASONS = {"barge_in", "session_stop", "timeout", "component_failure"}


@dataclass(slots=True)
class CancellationToken:
    """Idempotent, thread-visible cancellation state for one turn generation."""

    session_id: int
    turn_id: int
    generation: int
    reason: str | None = None
    cancelled_at_monotonic_ns: int | None = None
    cancelled_at_wall_utc: datetime | None = None
    _event: threading.Event = field(default_factory=threading.Event, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def request_id(self) -> str:
        return f"{self.session_id}:{self.turn_id}:{self.generation}"

    def cancel(self, reason: str) -> bool:
        if reason not in _REASONS:
            raise ValueError(f"unsupported cancellation reason: {reason}")
        with self._lock:
            if self._event.is_set():
                return False
            self.reason = reason
            self.cancelled_at_monotonic_ns = time.monotonic_ns()
            self.cancelled_at_wall_utc = datetime.now(timezone.utc)
            self._event.set()
            return True

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise TurnCancelled(self)


class TurnCancelled(Exception):
    def __init__(self, token: CancellationToken) -> None:
        super().__init__(f"turn {token.turn_id} generation {token.generation} cancelled")
        self.token = token
