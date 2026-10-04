"""SileroVadAdapter — M3-02 VAD 适配器（实现 ports.asr.VadPort）。

按 model-manifest §1 VAD 行（2026-09 master `silero_vad` 默认入口）。
按 implementation-contracts §18 deadline 表。

M3 阶段：CPU 推理（VAD 不抢 GPU）。
"""
from __future__ import annotations

import time
from typing import Iterable

import numpy as np

from cyberwife.ports.asr import AsrPort, AsrResult  # type: ignore
from cyberwife.infrastructure.structured_logger import StructuredLogger


class VadEvent:
    """VAD 端点事件。"""

    def __init__(self, start_ms: int, end_ms: int) -> None:
        self.start_ms = start_ms
        self.end_ms = end_ms

    def to_dict(self) -> dict:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms}


class VadPort:
    """端点检测抽象接口（M3 暴露，独立于 AsrPort）。"""

    def is_speech(self, audio_pcm: bytes, sample_rate: int = 16000) -> bool:
        ...

    def speech_timestamps(self, audio_pcm: bytes, sample_rate: int = 16000) -> list[VadEvent]:
        ...

    def health(self) -> dict:
        ...


class SileroVadAdapter(VadPort):
    """Silero VAD（2026-09 默认入口；hub master 不再暴露 silero_vad_v5 显式 callable）。"""

    _model = None
    _utils = None

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._logger = StructuredLogger(name="cyberwife.vad")
        if SileroVadAdapter._model is None:
            self._load()

    def _load(self) -> None:
        import torch

        t0 = time.time()
        model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )
        SileroVadAdapter._model = model
        SileroVadAdapter._utils = utils
        load_ms = int((time.time() - t0) * 1000)
        self._logger.emit(
            "vad.load",
            "vad",
            duration_ms=load_ms,
            device="cpu",
            runtime="torch.hub",
        )

    def is_speech(self, audio_pcm: bytes, sample_rate: int = 16000) -> bool:
        events = self.speech_timestamps(audio_pcm, sample_rate)
        return len(events) > 0

    def speech_timestamps(self, audio_pcm: bytes, sample_rate: int = 16000) -> list[VadEvent]:
        import torch

        if SileroVadAdapter._model is None:
            self._load()
        # 字节 → int16 → float32 [-1, 1]
        if sample_rate != self._sample_rate:
            # 简化：仅支持 16kHz；M3 阶段非 16kHz 不处理
            raise ValueError(f"only 16000Hz supported, got {sample_rate}")
        audio = np.frombuffer(audio_pcm, dtype=np.int16).astype(np.float32) / 32768.0
        audio_t = torch.from_numpy(audio)
        (get_speech_timestamps, _, _, _, _) = SileroVadAdapter._utils
        ts = get_speech_timestamps(audio_t, SileroVadAdapter._model, sampling_rate=sample_rate)
        return [VadEvent(int(e["start"] / sample_rate * 1000), int(e["end"] / sample_rate * 1000)) for e in ts]

    def health(self) -> dict:
        return {
            "status": "ready" if SileroVadAdapter._model is not None else "loading",
            "device": "cpu",
            "dtype": "fp32",
            "sample_rate": self._sample_rate,
        }
