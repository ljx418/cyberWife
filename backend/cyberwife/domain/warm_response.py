"""Strict, versioned policy objects for in-memory greeting responses."""
from __future__ import annotations

import re
from dataclasses import dataclass


ALLOWED_GREETINGS = frozenset(
    {"你好", "嗨", "早上好", "晚上好", "你在吗", "能听见吗", "谢谢", "再见"}
)
_TRAILING_PUNCTUATION = re.compile(r"[。！？!?，,；;]+$")
_WHITESPACE = re.compile(r"\s+")


def normalize_warm_text(text: str) -> str:
    normalized = _WHITESPACE.sub("", str(text).strip())
    return _TRAILING_PUNCTUATION.sub("", normalized)


@dataclass(frozen=True)
class WarmResponseContext:
    persona_version: str
    voice_version: str
    llm_revision: str
    tts_revision: str
    policy_version: str


@dataclass(frozen=True)
class WarmResponseKey:
    context: WarmResponseContext
    text: str


@dataclass(frozen=True)
class WarmResponseEntry:
    reply_text: str
    pcm_frames: tuple[bytes, ...]

    @property
    def size_bytes(self) -> int:
        return len(self.reply_text.encode("utf-8")) + sum(len(frame) for frame in self.pcm_frames)


class WarmResponsePolicy:
    def __init__(self, selected: tuple[str, ...] = ("你好",), *, version: str = "v1") -> None:
        normalized = tuple(normalize_warm_text(text) for text in selected)
        if not 1 <= len(normalized) <= 6:
            raise ValueError("warm greeting selection must contain 1 to 6 items")
        if len(set(normalized)) != len(normalized):
            raise ValueError("warm greeting selection contains duplicates")
        if any(text not in ALLOWED_GREETINGS for text in normalized):
            raise ValueError("warm greeting is outside the approved whitelist")
        self.selected = frozenset(normalized)
        self.version = str(version)

    def match(self, text: str) -> str | None:
        normalized = normalize_warm_text(text)
        return normalized if normalized in self.selected else None
