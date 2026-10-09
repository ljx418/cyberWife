"""TTS-to-audio-clock pipeline with non-blocking Avatar degradation."""
from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

from cyberwife.domain.cancellation import CancellationToken

class MediaPipeline:
    def __init__(self, tts, avatar=None, *, queue_size: int = 64) -> None:
        self._tts = tts
        self._avatar = avatar
        self._queue_size = queue_size
        # PyTorch/CosyVoice lazily creates native compute teams per calling
        # thread.  A shared asyncio executor therefore grows native task count
        # as turns land on different workers.  One owned inference thread also
        # matches the V1 single-conversation/single-GPU contract.
        self._tts_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="cyberwife-tts-inference",
        )
        self._control_executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="cyberwife-media-control",
        )
        self._close_lock = Lock()
        self._closed = False
        self._metrics = {
            "tts_queue_depth": 0,
            "tts_queue_capacity": queue_size,
            "first_audio_ms": None,
            "audio_frames": 0,
            "avatar_state": "disabled" if avatar is None else "connecting",
            "avatar_frame_errors": 0,
        }

    def metrics(self) -> dict:
        result = dict(self._metrics)
        if hasattr(self._tts, "last_metrics"):
            result["tts"] = dict(self._tts.last_metrics)
        return result

    def release_transient_memory(self) -> None:
        cleanup = getattr(self._tts, "release_transient_memory", None)
        if cleanup is not None:
            cleanup()

    async def release_transient_memory_async(self) -> None:
        """Serialize allocator cleanup behind inference on the owned worker."""
        if self._closed:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._tts_executor, self.release_transient_memory)

    async def _run_control(self, function, *args, **kwargs):
        if self._closed:
            raise RuntimeError("media pipeline is closed")
        call = functools.partial(function, *args, **kwargs)
        return await asyncio.get_running_loop().run_in_executor(self._control_executor, call)

    def close(self) -> None:
        """Idempotently release the owned TTS execution domain."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self._tts_executor.shutdown(wait=True, cancel_futures=True)
        self._control_executor.shutdown(wait=True, cancel_futures=True)

    async def cancel(self, token: CancellationToken) -> None:
        """Stop TTS and Avatar concurrently; browser playback is cancelled by event."""
        calls = []
        tts_cancel = getattr(self._tts, "cancel", None)
        if tts_cancel is not None:
            calls.append(self._run_control(tts_cancel, token.request_id))
        avatar_cancel = getattr(self._avatar, "cancel", None)
        if avatar_cancel is not None:
            calls.append(self._run_control(avatar_cancel))
        if calls:
            await asyncio.gather(*calls, return_exceptions=True)

    async def complete_avatar(self) -> None:
        """Close the current turn after all TTS segments have been emitted."""
        complete_audio = getattr(self._avatar, "complete_audio", None)
        if complete_audio is not None:
            try:
                await self._run_control(complete_audio)
            except Exception:
                self._metrics["avatar_frame_errors"] += 1

    async def stream_cached(
        self,
        frames: tuple[bytes, ...],
        *,
        origin_started: float | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[dict]:
        """Replay bounded precomputed PCM while preserving Avatar/audio clock."""
        started = origin_started or time.perf_counter()
        self._metrics["first_audio_ms"] = None
        self._metrics["audio_frames"] = 0
        avatar_ready = False
        consecutive_avatar_errors = 0
        if self._avatar is not None:
            try:
                begin_generation = getattr(self._avatar, "begin_generation", None)
                if begin_generation is not None and cancellation_token is not None:
                    begin_generation(cancellation_token.generation)
                await self._run_control(self._avatar.open)
                avatar_ready = True
                self._metrics["avatar_state"] = "ready"
            except Exception:
                self._metrics["avatar_state"] = "static_fallback"
        for index, frame in enumerate(frames):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            if len(frame) != 640:
                raise ValueError("cached PCM frame must be exactly 640 bytes")
            if self._metrics["first_audio_ms"] is None:
                self._metrics["first_audio_ms"] = round((time.perf_counter() - started) * 1000, 1)
            self._metrics["audio_frames"] += 1
            clock_ms = index * 20
            yield {"type": "reply.audio.chunk", "pcm": frame, "clock_ms": clock_ms}
            if avatar_ready:
                try:
                    await self._run_control(self._avatar.push_audio, frame, clock_ms=clock_ms)
                    consecutive_avatar_errors = 0
                except Exception:
                    consecutive_avatar_errors += 1
                    self._metrics["avatar_frame_errors"] += 1
                    if consecutive_avatar_errors >= 3:
                        avatar_ready = False
                        self._metrics["avatar_state"] = "static_fallback"
                        yield {"type": "media.state", "mode": "static_fallback", "reason": "avatar_unavailable"}

    async def stream(
        self,
        text: str,
        reference_audio_path: str,
        reference_transcript: str,
        *,
        origin_started: float | None = None,
        clock_offset_ms: int = 0,
        reset_metrics: bool = True,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[dict]:
        if self._closed:
            raise RuntimeError("media pipeline is closed")
        started = origin_started or time.perf_counter()
        if reset_metrics:
            self._metrics["first_audio_ms"] = None
            self._metrics["audio_frames"] = 0
        queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue(self._queue_size)
        loop = asyncio.get_running_loop()
        producer_stop = Event()

        def produce() -> None:
            try:
                # A V1 reply is already bounded by the prompt compiler.  Keep
                # it in one CosyVoice inference so sentence boundaries share
                # one prosody contour instead of restarting the voice for
                # every 4–17 character fragment.
                for frame in self._tts.synthesize_stream(
                    text, reference_audio_path, reference_transcript
                ):
                    if producer_stop.is_set() or (
                        cancellation_token is not None and cancellation_token.cancelled
                    ):
                        return
                    asyncio.run_coroutine_threadsafe(queue.put(("audio", frame)), loop).result()
            except BaseException as exc:
                asyncio.run_coroutine_threadsafe(queue.put(("error", exc)), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(("done", None)), loop).result()

        avatar_ready = False
        consecutive_avatar_errors = 0
        if self._avatar is not None:
            try:
                begin_generation = getattr(self._avatar, "begin_generation", None)
                if begin_generation is not None and cancellation_token is not None:
                    begin_generation(cancellation_token.generation)
                await self._run_control(self._avatar.open)
                avatar_ready = True
                self._metrics["avatar_state"] = "ready"
            except Exception:
                self._metrics["avatar_state"] = "static_fallback"
        producer = loop.run_in_executor(self._tts_executor, produce)
        clock_ms = clock_offset_ms
        try:
            while True:
                if cancellation_token is not None:
                    cancellation_token.raise_if_cancelled()
                kind, value = await queue.get()
                self._metrics["tts_queue_depth"] = queue.qsize()
                try:
                    if kind == "done":
                        break
                    if kind == "error":
                        yield {"type": "media.state", "mode": "text_only", "reason": "tts_unavailable"}
                        break
                    frame = bytes(value)
                    if self._metrics["first_audio_ms"] is None:
                        self._metrics["first_audio_ms"] = round((time.perf_counter() - started) * 1000, 1)
                    self._metrics["audio_frames"] += 1
                    yield {"type": "reply.audio.chunk", "pcm": frame, "clock_ms": clock_ms}
                    if avatar_ready:
                        try:
                            await self._run_control(self._avatar.push_audio, frame, clock_ms=clock_ms)
                            consecutive_avatar_errors = 0
                        except Exception:
                            consecutive_avatar_errors += 1
                            self._metrics["avatar_frame_errors"] += 1
                            if consecutive_avatar_errors >= 3:
                                avatar_ready = False
                                self._metrics["avatar_state"] = "static_fallback"
                                yield {"type": "media.state", "mode": "static_fallback", "reason": "avatar_unavailable"}
                    clock_ms += 20
                finally:
                    queue.task_done()
        finally:
            # Cancelling the asyncio wrapper does not stop a running executor
            # callable.  It can instead strand the worker in a thread-safe
            # bounded-queue put and deadlock executor shutdown.  Signal the
            # producer and drain pending frames until the owned callable exits.
            producer_stop.set()
            while not producer.done():
                try:
                    queue.get_nowait()
                    queue.task_done()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0)
            await asyncio.gather(producer, return_exceptions=True)
            self._metrics["tts_queue_depth"] = 0
