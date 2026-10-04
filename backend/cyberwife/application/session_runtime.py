"""Full-duplex WebSocket runtime with one turn and one serialized sender."""
from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass

from cyberwife.application.conversation_orchestrator import Event


@dataclass(slots=True)
class RuntimeSnapshot:
    active_turns: int
    outbound_depth: int
    outbound_capacity: int
    late_events_dropped: int


class SessionRuntime:
    def __init__(self, session_id: int, websocket, orchestrator, pipeline, *, queue_size: int = 128) -> None:
        self.session_id = session_id
        self._ws = websocket
        self._orchestrator = orchestrator
        self._pipeline = pipeline
        self._outbound: asyncio.PriorityQueue[tuple[int, int, Event | dict | None]] = (
            asyncio.PriorityQueue(maxsize=queue_size)
        )
        self._sequence = itertools.count()
        self._sender: asyncio.Task | None = None
        self._active_turn: asyncio.Task | None = None
        self._closed = False
        self._late_events_dropped = 0

    async def start(self) -> None:
        if self._sender is None:
            public_id = self._orchestrator.public_session_id(self.session_id)
            self._sender = asyncio.create_task(self._send_loop(), name=f"ws-sender-{public_id}")

    def snapshot(self) -> RuntimeSnapshot:
        return RuntimeSnapshot(
            active_turns=int(self._active_turn is not None and not self._active_turn.done()),
            outbound_depth=self._outbound.qsize(),
            outbound_capacity=self._outbound.maxsize,
            late_events_dropped=self._late_events_dropped,
        )

    async def send(self, event: Event | dict, *, priority: bool = False) -> None:
        if self._closed:
            return
        await self._outbound.put((0 if priority else 10, next(self._sequence), event))

    def _is_current(self, event: Event | dict) -> bool:
        if isinstance(event, Event):
            type_ = event.type
            payload = event.payload
        else:
            type_ = str(event.get("type", ""))
            payload = event.get("payload", {})
        if type_ in {"barge_in.detected", "turn.cancelled", "error"}:
            return True
        generation = payload.get("generation") if isinstance(payload, dict) else None
        return generation is None or generation == self._orchestrator.generation(self.session_id)

    async def _send_loop(self) -> None:
        while True:
            _priority, _seq, item = await self._outbound.get()
            try:
                if item is None:
                    return
                if not self._is_current(item):
                    self._late_events_dropped += 1
                    continue
                payload = item.to_dict() if isinstance(item, Event) else item
                await self._ws.send_json(payload)
            finally:
                self._outbound.task_done()

    async def start_turn(self, turn_id: int, pcm: bytes) -> bool:
        if self._active_turn is not None and not self._active_turn.done():
            return False

        async def consume() -> None:
            async for event in self._pipeline.run(self.session_id, turn_id, pcm):
                if self._is_current(event):
                    await self.send(event)
                else:
                    self._late_events_dropped += 1

        public_id = self._orchestrator.public_session_id(self.session_id)
        task = asyncio.create_task(consume(), name=f"turn-{public_id}-{turn_id}")
        self._active_turn = task

        def clear(completed: asyncio.Task) -> None:
            if self._active_turn is completed:
                self._active_turn = None

        task.add_done_callback(clear)
        return True

    async def interrupt(self, *, reason: str = "barge_in", expected_turn_id: int | None = None):
        session = self._orchestrator.get(self.session_id)
        active_turn_id = session.active_turn.id if session and session.active_turn else 0
        if (
            session is None
            or session.state.value not in {"thinking", "speaking"}
            or (expected_turn_id is not None and expected_turn_id != active_turn_id)
        ):
            return None
        detected = self._orchestrator.emit(
            self.session_id,
            "barge_in.detected",
            turn_id=active_turn_id or None,
            payload={
                "active_turn_id": active_turn_id,
                "audio_silence_ms": 0,
                "cancelled_components": ["llm", "tts", "playback", "avatar"],
            },
        )
        if detected is not None:
            await self.send(detected, priority=True)

        result = await self._pipeline.interrupt(self.session_id, reason=reason)
        active = self._active_turn
        if active is not None and not active.done():
            active.cancel()
            try:
                await asyncio.wait_for(asyncio.gather(active, return_exceptions=True), timeout=1.0)
            except asyncio.TimeoutError:
                pass
        if result.token is not None:
            cancelled = self._orchestrator.emit(
                self.session_id,
                "turn.cancelled",
                turn_id=result.token.turn_id,
                payload={
                    "cancelled_turn_id": result.token.turn_id,
                    "next_state": "listening",
                    "reason": reason,
                    "cancelled_generation": result.token.generation,
                    "current_generation": result.new_generation,
                    "component_errors": list(result.component_errors),
                },
            )
            if cancelled is not None:
                await self.send(cancelled, priority=True)
        return result

    async def close(self) -> None:
        if self._closed:
            return
        if self._active_turn is not None and not self._active_turn.done():
            await self.interrupt(reason="session_stop")
        self._closed = True
        if self._sender is not None:
            await self._outbound.put((100, next(self._sequence), None))
            await asyncio.gather(self._sender, return_exceptions=True)
        self._sender = None
        self._active_turn = None
