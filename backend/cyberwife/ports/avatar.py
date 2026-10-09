"""Avatar Port — 数字人抽象接口（FR-10/§5 第 7 步）。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class AvatarPort(ABC):
    """数字人（口型视频）接口；WebRTC host candidates only（M4 阶段落地）。"""

    @abstractmethod
    def start_session(self, avatar_image_path: str) -> str:
        """启动一个 LiveTalking 会话；返回 session_id。"""
        ...

    def open(self, session_id: str = "0") -> str:
        """Open the configured local Avatar session."""
        return self.start_session("")

    @abstractmethod
    def push_audio_chunk(self, session_id: str, pcm_frame: bytes) -> None:
        """推一段 20ms PCM 帧；LiveTalking 异步合成对应口型视频帧。"""
        ...

    @abstractmethod
    def end_session(self, session_id: str) -> None:
        ...

    def push_audio(self, pcm_frame: bytes, *, clock_ms: int) -> None:
        """Push one 20ms PCM frame using audio playback as master clock."""
        self.push_audio_chunk("0", pcm_frame)

    def cancel(self) -> None:
        """Discard queued media for the active generation."""

    def complete_audio(self) -> None:
        """Finish queued media and return the active generation to Idle."""

    def close(self) -> None:
        """Close the active local session."""

    @abstractmethod
    def health(self) -> dict:
        ...
