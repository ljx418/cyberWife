"""Bounded process-local cache for strict greeting audio."""
from __future__ import annotations

import threading

from cyberwife.domain.warm_response import (
    WarmResponseContext,
    WarmResponseEntry,
    WarmResponseKey,
    WarmResponsePolicy,
)


class WarmResponseCache:
    def __init__(self, policy: WarmResponsePolicy, *, max_bytes: int = 64 * 1024 * 1024) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self._policy = policy
        self._max_bytes = int(max_bytes)
        self._entries: dict[WarmResponseKey, WarmResponseEntry] = {}
        self._size_bytes = 0
        self._lock = threading.RLock()

    @property
    def policy_version(self) -> str:
        return self._policy.version

    @property
    def size_bytes(self) -> int:
        with self._lock:
            return self._size_bytes

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def put(
        self,
        text: str,
        context: WarmResponseContext,
        *,
        reply_text: str,
        pcm_frames: tuple[bytes, ...],
    ) -> bool:
        matched = self._policy.match(text)
        if matched is None or context.policy_version != self._policy.version:
            return False
        if not reply_text.strip() or not pcm_frames or any(len(frame) != 640 for frame in pcm_frames):
            return False
        key = WarmResponseKey(context=context, text=matched)
        entry = WarmResponseEntry(reply_text=reply_text.strip(), pcm_frames=tuple(pcm_frames))
        with self._lock:
            old = self._entries.get(key)
            projected = self._size_bytes - (old.size_bytes if old else 0) + entry.size_bytes
            if projected > self._max_bytes:
                return False
            self._entries[key] = entry
            self._size_bytes = projected
        return True

    def lookup(self, text: str, context: WarmResponseContext) -> WarmResponseEntry | None:
        return self.resolve(text, context)[0]

    def resolve(
        self, text: str, context: WarmResponseContext
    ) -> tuple[WarmResponseEntry | None, str]:
        matched = self._policy.match(text)
        if matched is None:
            return None, "normal"
        if context.policy_version != self._policy.version:
            return None, "config-invalid"
        with self._lock:
            entry = self._entries.get(WarmResponseKey(context=context, text=matched))
        return (entry, "cache-hit") if entry is not None else (None, "config-invalid")

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._size_bytes = 0
