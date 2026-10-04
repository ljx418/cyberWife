"""ASR Port — 语音识别抽象接口。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class AsrSegment:
    """One timestamped ASR segment; timestamps are never discarded."""

    start_ms: int
    end_ms: int
    text: str
    confidence: float


@dataclass
class AsrResult:
    """ASR 输出。"""

    text: str
    confidence: float  # 0..1
    language: str = "zh"
    is_partial: bool = False
    segments: tuple[AsrSegment, ...] = ()


class AsrPort(ABC):
    """语音识别接口（FR-08 ASR partial / final）。"""

    @abstractmethod
    def transcribe(self, audio_pcm: bytes, sample_rate: int = 16000) -> AsrResult:
        """同步转写一段 PCM Int16 LE 单声道音频。"""
        ...

    @abstractmethod
    def health(self) -> dict:
        """返回组件健康快照（status / last_probe / device / dtype / revision）。"""
        ...
