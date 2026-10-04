"""Single authority for turn generation invalidation and state recovery."""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable

from cyberwife.domain.cancellation import CancellationToken
from cyberwife.domain.conversation import SessionState


CancelHook = Callable[[CancellationToken], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class CancellationResult:
    changed: bool
    token: CancellationToken | None
    new_generation: int
    component_errors: tuple[str, ...] = ()


class InterruptionController:
    def __init__(self, orchestrator, *, component_timeout_s: float = 0.9) -> None:
        self._orchestrator = orchestrator
        self._active: dict[int, CancellationToken] = {}
        self._hooks: list[tuple[str, CancelHook]] = []
        self._locks: dict[int, asyncio.Lock] = {}
        self._component_timeout_s = component_timeout_s

    def add_hook(self, component: str, hook: CancelHook) -> None:
        self._hooks.append((component, hook))

    def register(self, session_id: int, turn_id: int, generation: int) -> CancellationToken:
        previous = self._active.get(session_id)
        if previous is not None and not previous.cancelled:
            raise RuntimeError("session already has an active cancellation token")
        token = CancellationToken(session_id, turn_id, generation)
        self._active[session_id] = token
        return token

    def current(self, session_id: int) -> CancellationToken | None:
        return self._active.get(session_id)

    def is_current(self, token: CancellationToken) -> bool:
        return (
            self._active.get(token.session_id) is token
            and not token.cancelled
            and self._orchestrator.generation(token.session_id) == token.generation
        )

    def complete(self, token: CancellationToken) -> None:
        if self._active.get(token.session_id) is token:
            self._active.pop(token.session_id, None)

    async def cancel(self, session_id: int, *, reason: str) -> CancellationResult:
        lock = self._locks.setdefault(session_id, asyncio.Lock())
        async with lock:
            token = self._active.get(session_id)
            if token is None:
                return CancellationResult(False, None, self._orchestrator.generation(session_id))
            changed = token.cancel(reason)
            if not changed:
                return CancellationResult(False, token, self._orchestrator.generation(session_id))

            new_generation = self._orchestrator.invalidate_generation(session_id)
            self._orchestrator.cancel_active_turn(session_id)
            errors: list[str] = []

            async def run_hook(component: str, hook: CancelHook) -> None:
                try:
                    async def invoke() -> None:
                        if inspect.iscoroutinefunction(hook):
                            await hook(token)
                            return
                        outcome = await asyncio.to_thread(hook, token)
                        if asyncio.iscoroutine(outcome):
                            await outcome

                    await asyncio.wait_for(invoke(), timeout=self._component_timeout_s)
                except asyncio.TimeoutError:
                    errors.append(f"{component}:timeout")
                except Exception:
                    errors.append(component)

            if self._hooks:
                await asyncio.gather(*(run_hook(name, hook) for name, hook in self._hooks))

            session = self._orchestrator.get(session_id)
            if session is not None:
                if session.state in {SessionState.THINKING, SessionState.SPEAKING}:
                    self._orchestrator.transition(session_id, SessionState.INTERRUPTED)
                if session.state == SessionState.INTERRUPTED:
                    self._orchestrator.transition(session_id, SessionState.LISTENING)
            return CancellationResult(changed, token, new_generation, tuple(sorted(errors)))
