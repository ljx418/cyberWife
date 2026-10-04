import asyncio
import time

import pytest

from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.interruption_controller import InterruptionController
from cyberwife.domain.cancellation import CancellationToken
from cyberwife.domain.conversation import SessionState


def test_cancellation_token_is_idempotent_and_records_two_clocks():
    token = CancellationToken(session_id=7, turn_id=3, generation=11)

    assert token.cancel("barge_in") is True
    first_monotonic = token.cancelled_at_monotonic_ns
    first_wall = token.cancelled_at_wall_utc
    assert token.cancel("timeout") is False

    assert token.cancelled is True
    assert token.reason == "barge_in"
    assert token.cancelled_at_monotonic_ns == first_monotonic
    assert token.cancelled_at_wall_utc == first_wall


@pytest.mark.asyncio
async def test_interruption_invalidates_generation_and_returns_to_listening():
    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    turn = orchestrator.begin_turn(session.id, 1)
    orchestrator.transition(session.id, SessionState.THINKING)
    controller = InterruptionController(orchestrator)
    token = controller.register(session.id, turn.id, orchestrator.generation(session.id))

    result = await controller.cancel(session.id, reason="barge_in")
    repeated = await controller.cancel(session.id, reason="barge_in")

    assert result.changed is True
    assert repeated.changed is False
    assert token.cancelled is True
    assert turn.status == "cancelled"
    assert orchestrator.generation(session.id) == token.generation + 1
    assert session.state == SessionState.LISTENING
    assert controller.is_current(token) is False


@pytest.mark.asyncio
async def test_interruption_marks_text_complete_but_still_playing_turn_cancelled():
    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    turn = orchestrator.begin_turn(session.id, 1)
    orchestrator.transition(session.id, SessionState.THINKING)
    orchestrator.complete_turn(session.id, "已生成但仍在播放")
    orchestrator.transition(session.id, SessionState.SPEAKING)
    controller = InterruptionController(orchestrator)
    controller.register(session.id, turn.id, orchestrator.generation(session.id))

    result = await controller.cancel(session.id, reason="barge_in")

    assert result.changed is True
    assert turn.status == "cancelled"
    assert session.state == SessionState.LISTENING


@pytest.mark.asyncio
async def test_slow_sync_cancel_hook_is_bounded_and_reported():
    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    turn = orchestrator.begin_turn(session.id, 1)
    orchestrator.transition(session.id, SessionState.THINKING)
    controller = InterruptionController(orchestrator, component_timeout_s=0.02)
    controller.register(session.id, turn.id, orchestrator.generation(session.id))
    controller.add_hook("slow", lambda _token: time.sleep(0.2))

    started = time.perf_counter()
    result = await controller.cancel(session.id, reason="barge_in")

    assert time.perf_counter() - started < 0.1
    assert result.component_errors == ("slow:timeout",)
    assert session.state == SessionState.LISTENING
