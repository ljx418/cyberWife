"""Bounded loopback H.264 output for browser WebCodecs consumers."""

from __future__ import annotations

import asyncio
import itertools
import threading
import time
from fractions import Fraction
from typing import Optional

import av
from av.video.frame import PictureType

from registry import register
from streamout.base_output import BaseOutput
from utils.logger import logger


HEADER_SIZE = 18
PROTOCOL_VERSION = 2


@register("streamout", "ws_h264")
class H264WebSocketOutput(BaseOutput):
    """Encode one Annex-B access unit per message and keep only two pending frames."""

    def __init__(self, opt=None, parent=None, **kwargs):
        super().__init__(opt, parent)
        self._codec = None
        self._codec_name = None
        self._width = 0
        self._height = 0
        self._sequence = 0
        self._started_at = None
        self._force_keyframe = True
        self._last_generation = None
        self._subscribers = {}
        self._ids = itertools.count(1)
        self._lock = threading.Lock()

    @property
    def codec_name(self) -> Optional[str]:
        return self._codec_name

    def start(self) -> None:
        # Start the media clock on the first emitted frame.  Starting it while
        # ASR/inference threads warm would make the encoder "catch up" in a
        # burst and violate the 25 FPS browser contract.
        self._started_at = None

    def subscribe(self, loop: asyncio.AbstractEventLoop):
        token = next(self._ids)
        queue = asyncio.Queue(maxsize=2)
        with self._lock:
            self._subscribers[token] = (loop, queue)
            self._force_keyframe = True
        return token, queue

    def unsubscribe(self, token: int) -> None:
        with self._lock:
            self._subscribers.pop(token, None)

    def _open_codec(self, width: int, height: int):
        errors = []
        for name, options in (
            ("h264_nvenc", {
                "preset": "p1", "tune": "ll", "zerolatency": "1",
                "rc": "cbr", "b": "1800k", "bf": "0", "g": "25",
                "forced-idr": "1", "repeat-headers": "1",
            }),
            ("libx264", {
                "preset": "ultrafast", "tune": "zerolatency", "crf": "24",
                "bf": "0", "g": "25", "repeat-headers": "1",
            }),
        ):
            try:
                codec = av.CodecContext.create(name, "w")
                codec.width = width
                codec.height = height
                codec.pix_fmt = "yuv420p"
                codec.time_base = Fraction(1, int(self.opt.fps))
                codec.framerate = Fraction(int(self.opt.fps), 1)
                codec.options = options
                codec.open()
                self._codec_name = name
                self._width = width
                self._height = height
                if self.parent is not None:
                    self.parent.media_metrics["video_codec"] = name
                    self.parent.media_metrics["video_queue_limit"] = 2
                logger.info("H.264 WebSocket encoder ready: %s %dx%d", name, width, height)
                return codec
            except Exception as error:
                errors.append(f"{name}: {error}")
        raise RuntimeError("no H.264 encoder available: " + "; ".join(errors))

    def _offer(self, queue: asyncio.Queue, payload: bytes) -> None:
        if queue.full():
            try:
                queue.get_nowait()
                if self.parent is not None:
                    self.parent.media_metrics["late_video_frames_dropped"] += 1
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass

    def _broadcast(self, payload: bytes) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers.values())
        for loop, queue in subscribers:
            if not loop.is_closed():
                loop.call_soon_threadsafe(self._offer, queue, payload)

    def push_video_frame(self, frame, *, generation: int = 0) -> None:
        fps = int(self.opt.fps)
        if self._started_at is None:
            self._started_at = time.perf_counter()
        target = self._started_at + self._sequence / fps
        delay = target - time.perf_counter()
        if delay > 0:
            time.sleep(delay)

        height, width = frame.shape[:2]
        if self._codec is None:
            self._codec = self._open_codec(width, height)
        video_frame = av.VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = self._sequence
        with self._lock:
            # Idle batches have no audio metadata and arrive as generation 0.
            # Once a real turn has established a generation, keep that value
            # across its idle frames so the browser's stale-frame fence does
            # not create timestamp holes or a frozen final pose.
            effective_generation = (
                self._last_generation
                if generation == 0 and self._last_generation not in {None, 0}
                else generation
            )
            generation_changed = self._last_generation != effective_generation
            force_keyframe = self._force_keyframe or generation_changed
            self._force_keyframe = False
            self._last_generation = effective_generation
        if force_keyframe:
            video_frame.pict_type = PictureType.I
        for packet in self._codec.encode(video_frame):
            flags = 1 if packet.is_keyframe else 0
            timestamp_ms = int(self._sequence * 1000 / fps) & 0xFFFFFFFF
            header = bytearray(HEADER_SIZE)
            header[0] = PROTOCOL_VERSION
            header[1] = flags
            header[2:4] = width.to_bytes(2, "little")
            header[4:6] = height.to_bytes(2, "little")
            header[6:10] = timestamp_ms.to_bytes(4, "little")
            header[10:14] = self._sequence.to_bytes(4, "little")
            header[14:18] = int(effective_generation).to_bytes(4, "little", signed=False)
            self._broadcast(bytes(header) + bytes(packet))
        self._sequence += 1

    def push_audio_frame(self, frame, eventpoint=None) -> None:
        # Gateway PCM is the sole browser audio path and playback clock.
        return None

    def get_buffer_size(self) -> int:
        with self._lock:
            queues = [queue for _, queue in self._subscribers.values()]
        return max((queue.qsize() for queue in queues), default=0)

    def stop(self) -> None:
        codec, self._codec = self._codec, None
        if codec is not None:
            try:
                codec.encode(None)
            except Exception:
                logger.debug("H.264 encoder flush failed during shutdown", exc_info=True)
        with self._lock:
            self._subscribers.clear()
