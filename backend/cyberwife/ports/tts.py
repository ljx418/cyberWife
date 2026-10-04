"""TTS Port — 声音克隆抽象接口（FR-05 voice clone）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class TtsPort(ABC):
    """声音克隆接口；按文本 + 引用音频 + 逐字稿生成 PCM Int16 LE 单声道 16kHz 流。"""

    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        reference_audio_path: str,
        reference_transcript: str,
        max_duration_s: float = 60.0,
    ) -> Iterator[bytes]:
        """yield 16kHz 单声道 PCM Int16 LE 帧（每帧 640 字节 = 20ms）。"""
        ...

    @abstractmethod
    def cancel(self, request_id: str) -> bool:
        ...

    @abstractmethod
    def health(self) -> dict:
        ...
