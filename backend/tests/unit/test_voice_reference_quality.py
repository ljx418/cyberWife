import struct
import wave
from pathlib import Path

import pytest

from cyberwife.application.voice_reference_quality import (
    character_error_rate,
    decode_reference_pcm16,
    validate_voice_reference,
)


def write_voice(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(struct.pack("<h", 1200) * 1600)


class SpeechStub:
    def __init__(self, text: str):
        self.text = text
        self.received = b""

    def transcribe(self, pcm: bytes, sample_rate: int):
        assert sample_rate == 16000
        self.received = pcm
        return {"speech_detected": True, "text": self.text}


def test_reference_validation_accepts_punctuation_only_differences(tmp_path: Path):
    voice = tmp_path / "voice.wav"
    write_voice(voice)
    speech = SpeechStub("这是一段经过授权的测试语音")
    result = validate_voice_reference(voice, "这是，一段经过授权的测试语音。", speech)
    assert result["cer"] == 0
    assert len(speech.received) % 640 == 0


def test_reference_validation_rejects_the_regressed_unrelated_transcript(tmp_path: Path):
    voice = tmp_path / "voice.wav"
    write_voice(voice)
    speech = SpeechStub("这是一段经过授权的测试语音")
    with pytest.raises(RuntimeError, match="voice_reference_transcript_mismatch"):
        validate_voice_reference(voice, "今天终于有一点空闲了，你想先聊什么", speech)


def test_reference_cer_is_not_confidence():
    assert character_error_rate("二加三等于五", "二加三等于五") == 0
    assert character_error_rate("二加三等于五", "天气很好") > 0.5


def test_reference_decoder_rejects_too_short_audio(tmp_path: Path):
    voice = tmp_path / "short.wav"
    with wave.open(str(voice), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(16000)
        output.writeframes(struct.pack("<h", 10) * 10)
    with pytest.raises(ValueError, match="shorter"):
        decode_reference_pcm16(voice)
