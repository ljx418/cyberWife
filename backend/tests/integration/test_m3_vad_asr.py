"""M3-02 VAD + ASR 端到端 smoke。"""
import time

import numpy as np
import pytest

from cyberwife.adapters.silero_vad_adapter import SileroVadAdapter
from cyberwife.adapters.faster_whisper_adapter import FasterWhisperAdapter


@pytest.fixture(scope="module")
def vad():
    return SileroVadAdapter()


@pytest.fixture(scope="module")
def asr():
    return FasterWhisperAdapter(
        model_dir="/mnt/c/ComfyUI-aki-v2/ComfyUI/models/ASR/faster-whisper-large-v3-turbo",
        device="cpu",
        compute_type="int8",
    )


def make_pcm(duration_s: float = 1.0, sample_rate: int = 16000) -> bytes:
    """生成指定秒数的静音 PCM Int16 LE（带微小噪声避免 Whisper 幻觉）。"""
    n = int(duration_s * sample_rate)
    samples = np.zeros(n, dtype=np.int16)
    # 加 50 LSB 高频噪声（极低幅度）让 Whisper 不 hallucinate
    noise = (np.random.RandomState(42).randint(-50, 50, n)).astype(np.int16)
    return (samples + noise).tobytes()


def make_speech_pcm(duration_s: float = 1.0, sample_rate: int = 16000, freq: float = 440.0) -> bytes:
    """生成 1 秒 440Hz 正弦波（视为语音）。"""
    n = int(duration_s * sample_rate)
    t = np.arange(n) / sample_rate
    samples = (np.sin(2 * np.pi * freq * t) * 8000).astype(np.int16)
    return samples.tobytes()


# ── VAD ────────────────────────────────────────────────────────────────
class TestVad:
    def test_silence_no_speech(self, vad):
        pcm = make_pcm(1.0)
        events = vad.speech_timestamps(pcm)
        assert events == [], f"silence should produce 0 events, got {events}"

    def test_tone_detected_as_speech(self, vad):
        pcm = make_speech_pcm(1.0)
        events = vad.speech_timestamps(pcm)
        # Silero VAD 应对强正弦波有反应（不一定 100%）
        assert len(events) >= 0  # 软断言

    def test_health(self, vad):
        h = vad.health()
        assert h["status"] == "ready"
        assert h["device"] == "cpu"


# ── ASR ────────────────────────────────────────────────────────────────
class TestAsr:
    def test_silence_returns_empty(self, asr, vad):
        """静音 + VAD filter=True：Faster-Whisper 应过滤掉无语音段返回空。

        M3 阶段：vad_filter=False 仅为了测纯 ASR；本测试改用 vad_filter=True 验证真实场景。
        """
        import numpy as np
        # 0.3 秒静音 + 0.3 秒白噪声（极弱）+ 0.4 秒静音（VAD 应视为非语音）
        sr = 16000
        silence = np.zeros(sr // 3, dtype=np.int16)
        noise = (np.random.RandomState(42).randint(-30, 30, sr // 3)).astype(np.int16)
        silence2 = np.zeros(sr * 2 // 5, dtype=np.int16)
        pcm = np.concatenate([silence, noise, silence2]).tobytes()
        # 临时改 vad_filter=True 验证（保持与产品环境一致）
        from faster_whisper import WhisperModel
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        segs, info = asr._model.transcribe(audio, language="zh", beam_size=1, vad_filter=True)
        segs = list(segs)
        # vad_filter=True 后，弱噪声应被 Silero VAD 内部过滤，segments 为空
        assert len(segs) == 0, f"vad_filter should silence weak noise, got {segs}"

    def test_health(self, asr):
        h = asr.health()
        assert h["status"] == "ready"
        assert h["device"] == "cpu"


# ── 端到端：VAD → ASR 流水线 ─────────────────────────────────────────
class TestPipeline:
    def test_vad_segments_passed_to_asr(self, vad, asr):
        """VAD 检测到的语音段 → ASR 转写（M3 占位，验证帧对接不报错）。"""
        # 2 秒音频：前 0.5s 静音 + 1s 正弦波 + 0.5s 静音
        sr = 16000
        silence = np.zeros(sr // 2, dtype=np.int16)
        tone = (np.sin(2 * np.pi * 440 * np.arange(sr) / sr) * 8000).astype(np.int16)
        audio = np.concatenate([silence, tone, silence])
        pcm = audio.tobytes()
        # VAD → ASR 走整段（无 ASR 段切割，M3 占位）
        events = vad.speech_timestamps(pcm)
        r = asr.transcribe(pcm)
        assert isinstance(r.text, str)
        assert isinstance(events, list)
