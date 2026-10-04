"""B1 real audio-to-text TurnPipeline.

All blocking inference stays outside the asyncio event loop.  Queues are
bounded, and emitted events keep one session/turn/trace identity.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import threading
import time
from collections.abc import AsyncIterator, Callable
from typing import Any

from cyberwife.application.conversation_orchestrator import (
    ConversationOrchestrator,
    Event,
    gen_trace_id,
)
from cyberwife.application.output_sanitizer import OutputSanitizer
from cyberwife.application.prompt_compiler import PromptCompiler
from cyberwife.application.sentence_scheduler import playable_prefix
from cyberwife.application.interruption_controller import InterruptionController
from cyberwife.domain.cancellation import CancellationToken, TurnCancelled
from cyberwife.domain.conversation import SessionState
from cyberwife.application.runtime_metrics import RuntimeMetrics
from cyberwife.ports.observability import RuntimeMetricsPort, StructuredLoggerPort


class _NullStructuredLogger:
    def emit(self, event: str, component: str, **fields: Any) -> dict:
        return {"event": event, "component": component, **fields}


class TurnPipeline:
    def __init__(
        self,
        orchestrator: ConversationOrchestrator,
        speech_runtime: Any,
        llm: Any,
        prompt_compiler: PromptCompiler,
        sanitizer: OutputSanitizer,
        *,
        repository=None,
        profile_provider: Callable[[], dict] | None = None,
        media_pipeline=None,
        voice_reference_provider: Callable[[], tuple[str, str]] | None = None,
        asr_deadline_s: float = 120.0,
        llm_deadline_s: float = 60.0,
        llm_queue_size: int = 32,
        runtime_metrics: RuntimeMetricsPort | None = None,
        logger: StructuredLoggerPort | None = None,
        first_playable_min_chars: int = 10,
        warm_response_cache=None,
        warm_context_provider: Callable[[], Any] | None = None,
        memory_provider: Callable[[str], list[tuple[str, float]]] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._speech = speech_runtime
        self._llm = llm
        self._compiler = prompt_compiler
        self._sanitizer = sanitizer
        self._repository = repository
        self._profile_provider = profile_provider or (lambda: {})
        self._media = media_pipeline
        self._voice_reference_provider = voice_reference_provider
        self._asr_deadline_s = asr_deadline_s
        self._llm_deadline_s = llm_deadline_s
        self._llm_queue_size = llm_queue_size
        self._runtime_metrics = runtime_metrics or RuntimeMetrics()
        if not 4 <= first_playable_min_chars <= 18:
            raise ValueError("first_playable_min_chars must be between 4 and 18")
        self._first_playable_min_chars = first_playable_min_chars
        self._warm_response_cache = warm_response_cache
        self._warm_context_provider = warm_context_provider
        self._memory_provider = memory_provider
        self._logger = logger or _NullStructuredLogger()
        self._active_turns = 0
        self._llm_queue_depth = 0
        self._llm_queue_max_observed = 0
        self._llm_chunks_produced = 0
        self._llm_chunks_consumed = 0
        self._llm_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="cyberwife-llm-stream",
        )
        self._close_lock = threading.Lock()
        self._closed = False
        self._interruptions = InterruptionController(orchestrator)
        self._interruptions.add_hook("llm", self._cancel_llm)
        if self._media is not None:
            self._interruptions.add_hook("media", self._cancel_media)

    def close(self) -> None:
        """Idempotently release the owned blocking LLM execution domain."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self._llm_executor.shutdown(wait=True, cancel_futures=True)

    def _cancel_llm(self, token: CancellationToken) -> None:
        cancel = getattr(self._llm, "cancel", None)
        if cancel is not None:
            cancel(token.request_id)

    async def _cancel_media(self, token: CancellationToken) -> None:
        cancel = getattr(self._media, "cancel", None)
        if cancel is not None:
            outcome = cancel(token)
            if asyncio.iscoroutine(outcome):
                await outcome

    async def interrupt(self, session_id: int, *, reason: str = "barge_in"):
        result = await self._interruptions.cancel(session_id, reason=reason)
        if result.changed and self._repository is not None:
            session = self._orchestrator.get(session_id)
            if (
                session is not None
                and session.active_turn is not None
                and session.recording_policy.value == "standard"
            ):
                await asyncio.to_thread(
                    self._repository.update_turn,
                    session.active_turn,
                    persist_text=session.recording_policy.value == "standard",
                )
        return result

    def complete_playback(self, session_id: int, generation: int) -> Event | None:
        token = self._interruptions.current(session_id)
        if token is None or token.generation != generation or token.cancelled:
            return None
        session = self._orchestrator.get(session_id)
        if session is None or session.state != SessionState.SPEAKING:
            return None
        self._orchestrator.transition(session_id, SessionState.LISTENING)
        self._interruptions.complete(token)
        return self._orchestrator.emit(
            session_id,
            "state.changed",
            turn_id=token.turn_id,
            payload={
                "previous": "speaking",
                "current": "listening",
                "reason": "playback_complete",
                "generation": generation,
            },
        )

    def is_generation_current(self, session_id: int, generation: int) -> bool:
        token = self._interruptions.current(session_id)
        return (
            self._orchestrator.generation(session_id) == generation
            and (token is None or (token.generation == generation and not token.cancelled))
        )

    def metrics(self) -> dict:
        metrics = {
            "active_turns": self._active_turns,
            "llm_queue_depth": self._llm_queue_depth,
            "llm_queue_max_observed": self._llm_queue_max_observed,
            "llm_queue_capacity": self._llm_queue_size,
            "llm_chunks_produced": self._llm_chunks_produced,
            "llm_chunks_consumed": self._llm_chunks_consumed,
        }
        if self._media is not None:
            metrics["media"] = self._media.metrics()
        metrics["latency"] = self._runtime_metrics.snapshot()
        return metrics

    def confirm_playback(
        self,
        *,
        trace_id: str,
        session_id: int,
        turn_id: int,
        generation: int,
        asr_to_playback_ms: float,
        browser_first_non_silent_wall_ms: float,
    ) -> bool:
        """Accept a browser-observed first-non-silent marker for this generation."""
        if self._orchestrator.generation(session_id) != generation:
            return False
        session = self._orchestrator.get(session_id)
        metric_session_id = (
            session_id
            if session is not None and session.recording_policy.value == "standard"
            else 0
        )
        return self._runtime_metrics.confirm_playback(
            trace_id=trace_id,
            session_id=metric_session_id,
            turn_id=turn_id,
            generation=generation,
            asr_to_playback_ms=asr_to_playback_ms,
            browser_first_non_silent_wall_ms=browser_first_non_silent_wall_ms,
        )

    async def _llm_chunks(self, prompt: str, token: CancellationToken) -> AsyncIterator[str]:
        if self._closed:
            raise RuntimeError("turn pipeline is closed")
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue(maxsize=self._llm_queue_size)

        def produce() -> None:
            def publish(item: tuple[str, Any]) -> bool:
                future = asyncio.run_coroutine_threadsafe(queue.put(item), loop)
                while True:
                    try:
                        future.result(timeout=0.05)
                        return True
                    except concurrent.futures.TimeoutError:
                        if token.cancelled:
                            future.cancel()
                            return False

            try:
                kwargs = {
                    "max_tokens": 96,
                    "temperature": 0.7,
                    "stop": ["<|im_end|>"],
                }
                parameters = inspect.signature(self._llm.generate_stream).parameters.values()
                if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters) or any(
                    p.name == "request_id" for p in parameters
                ):
                    kwargs["request_id"] = token.request_id
                iterator = self._llm.generate_stream(prompt, **kwargs)
                for chunk in iterator:
                    if token.cancelled:
                        break
                    if not publish(("chunk", chunk)):
                        break
                    self._llm_chunks_produced += 1
                    self._llm_queue_depth = max(
                        queue.qsize(), self._llm_chunks_produced - self._llm_chunks_consumed
                    )
                    self._llm_queue_max_observed = max(
                        self._llm_queue_max_observed, 1, self._llm_queue_depth
                    )
            except BaseException as exc:
                if not token.cancelled:
                    publish(("error", exc))
            finally:
                publish(("done", None))

        producer = loop.run_in_executor(self._llm_executor, produce)
        try:
            async with asyncio.timeout(self._llm_deadline_s):
                while True:
                    token.raise_if_cancelled()
                    kind, value = await queue.get()
                    if kind == "chunk":
                        self._llm_chunks_consumed += 1
                    self._llm_queue_depth = max(
                        queue.qsize(), self._llm_chunks_produced - self._llm_chunks_consumed
                    )
                    try:
                        if kind == "chunk":
                            yield str(value)
                        elif kind == "error":
                            raise RuntimeError("llm_stream_failed") from value
                        else:
                            break
                    finally:
                        queue.task_done()
        finally:
            await asyncio.gather(producer, return_exceptions=True)

    async def run(self, session_id: int, turn_id: int, pcm: bytes) -> AsyncIterator[Event]:
        trace_id = gen_trace_id()
        started = time.perf_counter()
        session = self._orchestrator.get(session_id)
        if session is None:
            raise KeyError(session_id)
        self._active_turns += 1
        media_task: asyncio.Task | None = None
        try:
            speech = await asyncio.wait_for(
                asyncio.to_thread(self._speech.transcribe, pcm, 16000),
                timeout=self._asr_deadline_s,
            )
            if not speech.get("speech_detected") or not str(speech.get("text", "")).strip():
                event = self._orchestrator.emit(
                    session_id,
                    "transcript.partial",
                    turn_id=None,
                    payload={
                        "text": "",
                        "confidence": 0.0,
                        "kind": "user",
                        "language": "zh",
                        "trace_id": trace_id,
                        "speech_detected": False,
                        "generation": self._orchestrator.generation(session_id),
                    },
                )
                if event:
                    yield event
                return

            turn = self._orchestrator.begin_turn(session_id, turn_id)
            generation = self._orchestrator.generation(session_id)
            token = self._interruptions.register(session_id, turn.id, generation)
            turn.user_text = str(speech["text"]).strip()
            turn.status = "streaming"
            cached_entry = None
            latency_bucket = "normal"
            if self._warm_response_cache is not None and self._warm_context_provider is not None:
                cached_entry, latency_bucket = self._warm_response_cache.resolve(
                    turn.user_text,
                    self._warm_context_provider(),
                )
            if self._repository is not None and session.recording_policy.value == "standard":
                await asyncio.to_thread(
                    self._repository.create_turn,
                    turn,
                    persist_text=session.recording_policy.value == "standard",
                )

            utterance_final_at = time.perf_counter()
            asr_final_wall_ms = time.time() * 1000
            self._runtime_metrics.begin(
                trace_id=trace_id,
                session_id=session_id if session.recording_policy.value == "standard" else 0,
                turn_id=turn.id,
                generation=generation,
                bucket=latency_bucket,
                asr_final_wall_ms=asr_final_wall_ms,
                at=utterance_final_at,
            )
            transcript = self._orchestrator.emit(
                session_id,
                "transcript.final",
                turn_id=turn.id,
                payload={
                    "text": turn.user_text,
                    "confidence": float(speech.get("confidence", 0.0)),
                    "kind": "user",
                    "language": str(speech.get("language", "zh")),
                    "segments": speech.get("segments", []),
                    "trace_id": trace_id,
                    "generation": generation,
                    "asr_final_wall_ms": asr_final_wall_ms,
                },
            )
            if transcript:
                yield transcript
            previous = session.state
            if not self._orchestrator.transition(session_id, SessionState.THINKING):
                raise RuntimeError("illegal_state_transition")
            state = self._orchestrator.emit(
                session_id,
                "state.changed",
                turn_id=turn.id,
                payload={
                    "previous": previous.value,
                    "current": SessionState.THINKING.value,
                    "reason": "transcript_final",
                    "trace_id": trace_id,
                    "generation": generation,
                },
            )
            if state:
                yield state

            if cached_entry is not None:
                cached_audio_emitted = False
                token.raise_if_cancelled()
                self._runtime_metrics.mark(trace_id, "llm_playable")
                delta = self._orchestrator.emit(
                    session_id,
                    "reply.text.delta",
                    turn_id=turn.id,
                    payload={
                        "stream_kind": "text_delta",
                        "text_delta": cached_entry.reply_text,
                        "trace_id": trace_id,
                        "generation": generation,
                    },
                )
                if delta:
                    yield delta
                self._orchestrator.complete_turn(session_id, cached_entry.reply_text)
                if (
                    self._repository is not None
                    and session.recording_policy.value == "standard"
                    and self._interruptions.is_current(token)
                ):
                    await asyncio.to_thread(
                        self._repository.update_turn,
                        turn,
                        persist_text=session.recording_policy.value == "standard",
                    )
                token.raise_if_cancelled()
                previous = session.state
                if not self._orchestrator.transition(session_id, SessionState.SPEAKING):
                    raise RuntimeError("illegal_state_transition")
                speaking = self._orchestrator.emit(
                    session_id,
                    "state.changed",
                    turn_id=turn.id,
                    payload={
                        "previous": previous.value,
                        "current": "speaking",
                        "reason": "warm_response_ready",
                        "trace_id": trace_id,
                        "generation": generation,
                    },
                )
                if speaking:
                    yield speaking
                final = self._orchestrator.emit(
                    session_id,
                    "reply.text.final",
                    turn_id=turn.id,
                    payload={
                        "stream_kind": "text_final",
                        "text_final": cached_entry.reply_text,
                        "trace_id": trace_id,
                        "generation": generation,
                    },
                )
                if final:
                    yield final
                if self._media is not None:
                    async for media in self._media.stream_cached(
                        cached_entry.pcm_frames,
                        origin_started=utterance_final_at,
                        cancellation_token=token,
                    ):
                        if media["type"] == "reply.audio.chunk":
                            cached_audio_emitted = True
                            import base64

                            self._runtime_metrics.mark(trace_id, "tts_first_packet")
                            event = self._orchestrator.emit(
                                session_id,
                                "reply.audio.chunk",
                                turn_id=turn.id,
                                payload={
                                    "stream_kind": "audio_chunk",
                                    "audio_chunk_b64": base64.b64encode(media["pcm"]).decode("ascii"),
                                    "sample_rate": 16000,
                                    "clock_ms": media["clock_ms"],
                                    "trace_id": trace_id,
                                    "generation": generation,
                                    "asr_final_wall_ms": asr_final_wall_ms,
                                    "server_elapsed_ms": (time.perf_counter() - utterance_final_at) * 1000,
                                },
                            )
                        else:
                            event = self._orchestrator.emit(
                                session_id,
                                "media.state",
                                turn_id=turn.id,
                                payload={**media, "trace_id": trace_id, "generation": generation},
                            )
                        if event:
                            yield event
                if cached_audio_emitted:
                    complete = self._orchestrator.emit(
                        session_id,
                        "reply.audio.complete",
                        turn_id=turn.id,
                        payload={"trace_id": trace_id, "generation": generation},
                    )
                    if complete:
                        yield complete
                    return
                token.raise_if_cancelled()
                previous = session.state
                self._orchestrator.transition(session_id, SessionState.LISTENING)
                listening = self._orchestrator.emit(
                    session_id,
                    "state.changed",
                    turn_id=turn.id,
                    payload={
                        "previous": previous.value,
                        "current": "listening",
                        "reason": "warm_response_complete",
                        "trace_id": trace_id,
                        "generation": generation,
                    },
                )
                if listening:
                    yield listening
                self._interruptions.complete(token)
                return

            profile = self._profile_provider() or {}
            memories: list[tuple[str, float]] = []
            if self._memory_provider is not None:
                memories = await asyncio.to_thread(self._memory_provider, turn.user_text)
                token.raise_if_cancelled()
            compiled = self._compiler.compile(
                profile=profile,
                memories=memories,
                user_input=turn.user_text,
            )
            prompt = self._compiler.to_chatml(compiled)
            raw = ""
            emitted = ""
            spoken_prefix = ""
            prefix_clock_ms = 0
            audio_emitted = False
            media_queue: asyncio.Queue[dict | None] = asyncio.Queue()

            async def produce_early_media(prefix: str) -> None:
                if self._media is None or self._voice_reference_provider is None:
                    return
                reference_audio, reference_text = self._voice_reference_provider()
                async for media_item in self._media.stream(
                    prefix,
                    reference_audio,
                    reference_text,
                    origin_started=utterance_final_at,
                    cancellation_token=token,
                ):
                    await media_queue.put(media_item)
                await media_queue.put(None)

            def media_event(media_item: dict, *, clock_offset: int = 0):
                nonlocal audio_emitted
                if media_item["type"] == "reply.audio.chunk":
                    audio_emitted = True
                    import base64
                    self._runtime_metrics.mark(trace_id, "tts_first_packet")
                    server_elapsed_ms = (time.perf_counter() - utterance_final_at) * 1000
                    return self._orchestrator.emit(
                        session_id,
                        "reply.audio.chunk",
                        turn_id=turn.id,
                        payload={
                            "stream_kind": "audio_chunk",
                            "audio_chunk_b64": base64.b64encode(media_item["pcm"]).decode("ascii"),
                            "sample_rate": 16000,
                            "clock_ms": media_item["clock_ms"] + clock_offset,
                            "trace_id": trace_id,
                            "generation": generation,
                            "asr_final_wall_ms": asr_final_wall_ms,
                            "server_elapsed_ms": server_elapsed_ms,
                        },
                    )
                return self._orchestrator.emit(
                    session_id,
                    "media.state",
                    turn_id=turn.id,
                    payload={**media_item, "trace_id": trace_id, "generation": generation},
                )

            async for chunk in self._llm_chunks(prompt, token):
                token.raise_if_cancelled()
                raw += chunk
                cleaned = self._sanitizer.clean(raw)
                if cleaned.startswith(emitted) and len(cleaned) > len(emitted):
                    delta = cleaned[len(emitted):]
                    if len(delta) >= 12 or cleaned.endswith(("。", "！", "？", "!", "?")):
                        emitted = cleaned
                        event = self._orchestrator.emit(
                            session_id,
                            "reply.text.delta",
                            turn_id=turn.id,
                            payload={
                                "stream_kind": "text_delta",
                                "text_delta": delta,
                                "trace_id": trace_id,
                                "generation": generation,
                            },
                        )
                        if event:
                            yield event
                if media_task is None and self._media is not None:
                    # CosyVoice performs poorly on very short fragments.  Ten
                    # Chinese characters is the measured latency/quality floor;
                    # subsequent text generation continues concurrently.
                    prefix = playable_prefix(
                        cleaned,
                        min_chars=self._first_playable_min_chars,
                    )
                    if prefix is not None:
                        spoken_prefix = prefix
                        self._runtime_metrics.mark(trace_id, "llm_playable")
                        media_task = asyncio.create_task(produce_early_media(spoken_prefix))
                while not media_queue.empty():
                    media_item = media_queue.get_nowait()
                    try:
                        if media_item is not None:
                            if media_item["type"] == "reply.audio.chunk":
                                prefix_clock_ms = max(prefix_clock_ms, int(media_item["clock_ms"]) + 20)
                            event = media_event(media_item)
                            if event:
                                yield event
                    finally:
                        media_queue.task_done()
            final_text = self._sanitizer.clean(raw)
            token.raise_if_cancelled()
            if not final_text:
                raise RuntimeError("empty_llm_response")
            # A short final response can become playable without crossing the
            # early-media threshold; it still needs an LLM playable marker.
            self._runtime_metrics.mark(trace_id, "llm_playable")
            if final_text.startswith(emitted) and len(final_text) > len(emitted):
                event = self._orchestrator.emit(
                    session_id,
                    "reply.text.delta",
                    turn_id=turn.id,
                    payload={
                        "stream_kind": "text_delta",
                        "text_delta": final_text[len(emitted):],
                        "trace_id": trace_id,
                        "generation": generation,
                    },
                )
                if event:
                    yield event
            self._orchestrator.complete_turn(session_id, final_text)
            if (
                self._repository is not None
                and session.recording_policy.value == "standard"
                and self._interruptions.is_current(token)
            ):
                await asyncio.to_thread(
                    self._repository.update_turn,
                    turn,
                    persist_text=session.recording_policy.value == "standard",
                )

            token.raise_if_cancelled()
            previous = session.state
            if not self._orchestrator.transition(session_id, SessionState.SPEAKING):
                raise RuntimeError("illegal_state_transition")
            state = self._orchestrator.emit(
                session_id,
                "state.changed",
                turn_id=turn.id,
                payload={
                    "previous": previous.value,
                    "current": "speaking",
                    "reason": "text_ready",
                    "trace_id": trace_id,
                    "generation": generation,
                },
            )
            if state:
                yield state
            final = self._orchestrator.emit(
                session_id,
                "reply.text.final",
                turn_id=turn.id,
                payload={
                    "stream_kind": "text_final",
                    "text_final": final_text,
                    "trace_id": trace_id,
                    "generation": generation,
                },
            )
            if final:
                yield final
            if media_task is not None:
                # Consume while synthesis is still running. Waiting for the
                # producer first turns a streaming TTS into whole-prefix
                # blocking and adds the complete synthesis wall time to first
                # sound.
                while True:
                    media_item = await media_queue.get()
                    try:
                        if media_item is None:
                            break
                        if media_item["type"] == "reply.audio.chunk":
                            prefix_clock_ms = max(prefix_clock_ms, int(media_item["clock_ms"]) + 20)
                        event = media_event(media_item)
                        if event:
                            yield event
                    finally:
                        media_queue.task_done()
                await media_task
            if self._media is not None and self._voice_reference_provider is not None:
                reference_audio, reference_text = self._voice_reference_provider()
                remainder = final_text[len(spoken_prefix):].strip()
                if remainder:
                    async for media in self._media.stream(
                        remainder,
                        reference_audio,
                        reference_text,
                        origin_started=utterance_final_at,
                        clock_offset_ms=prefix_clock_ms,
                        reset_metrics=not spoken_prefix,
                        cancellation_token=token,
                    ):
                        event = media_event(media)
                        if event:
                            yield event
            token.raise_if_cancelled()
            if audio_emitted:
                complete = self._orchestrator.emit(
                    session_id,
                    "reply.audio.complete",
                    turn_id=turn.id,
                    payload={"trace_id": trace_id, "generation": generation},
                )
                if complete:
                    yield complete
            else:
                previous = session.state
                self._orchestrator.transition(session_id, SessionState.LISTENING)
                listening = self._orchestrator.emit(
                    session_id,
                    "state.changed",
                    turn_id=turn.id,
                    payload={
                        "previous": previous.value,
                        "current": "listening",
                        "reason": "text_complete",
                        "trace_id": trace_id,
                        "generation": generation,
                    },
                )
                if listening:
                    yield listening
                self._interruptions.complete(token)
            self._logger.emit(
                "turn.completed",
                "turn_pipeline",
                session_id=(str(session_id) if session.recording_policy.value == "standard" else None),
                turn_id=turn.id,
                trace_id=trace_id,
                duration_ms=round((time.perf_counter() - started) * 1000),
                input_chars=len(turn.user_text),
                output_chars=len(final_text),
            )
        except TurnCancelled:
            return
        except Exception as exc:
            session = self._orchestrator.get(session_id)
            if session is not None:
                session.state = SessionState.ERROR
            self._logger.emit(
                "turn.failed",
                "turn_pipeline",
                level="ERROR",
                session_id=(
                    str(session_id)
                    if session is not None and session.recording_policy.value == "standard"
                    else None
                ),
                turn_id=turn_id,
                trace_id=trace_id,
                duration_ms=round((time.perf_counter() - started) * 1000),
                error_code=type(exc).__name__,
            )
            error = self._orchestrator.emit(
                session_id,
                "error",
                turn_id=turn_id,
                payload={
                    "code": "internal.error",
                    "message": "turn pipeline failed",
                    "user_action": "retry_later",
                    "trace_id": trace_id,
                },
            )
            if error:
                yield error
        finally:
            if media_task is not None and not media_task.done():
                media_task.cancel()
            if media_task is not None:
                await asyncio.gather(media_task, return_exceptions=True)
            self._active_turns = max(0, self._active_turns - 1)
            self._llm_queue_depth = 0
            if self._media is not None and hasattr(self._media, "release_transient_memory"):
                async_cleanup = getattr(self._media, "release_transient_memory_async", None)
                if async_cleanup is not None:
                    await async_cleanup()
                else:
                    await asyncio.to_thread(self._media.release_transient_memory)
