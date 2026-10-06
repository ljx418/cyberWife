"""Fail-closed quality gate for zero-shot TTS reference audio/text pairs."""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np


_TEXT_NOISE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")


def normalize_reference_text(text: str) -> str:
    return _TEXT_NOISE.sub("", text).lower()


def character_error_rate(reference: str, hypothesis: str) -> float:
    expected = normalize_reference_text(reference)
    actual = normalize_reference_text(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    previous = list(range(len(actual) + 1))
    for row, expected_char in enumerate(expected, 1):
        current = [row]
        for column, actual_char in enumerate(actual, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected_char != actual_char),
                )
            )
        previous = current
    return previous[-1] / len(expected)


def decode_reference_pcm16(path: str | Path) -> bytes:
    import soundfile as sf
    from scipy.signal import resample_poly

    samples, sample_rate = sf.read(str(path), dtype="float32", always_2d=True)
    mono = samples.mean(axis=1)
    if sample_rate != 16000:
        divisor = math.gcd(int(sample_rate), 16000)
        mono = resample_poly(mono, 16000 // divisor, int(sample_rate) // divisor).astype(np.float32)
    pcm = np.clip(mono, -1.0, 1.0).__mul__(32767.0).astype(np.int16).tobytes()
    if len(pcm) < 640:
        raise ValueError("voice reference is shorter than 20ms")
    if len(pcm) > 16000 * 2 * 30:
        raise ValueError("voice reference exceeds 30 seconds")
    return pcm + (b"\0" * ((-len(pcm)) % 640))


def validate_voice_reference(
    audio_path: str | Path,
    transcript: str,
    speech_runtime,
    *,
    max_cer: float = 0.15,
) -> dict[str, float | int | str]:
    """Transcribe the reference and reject a mismatched cloning transcript.

    The result deliberately omits both strings so health logs and reports do
    not retain private voice content.
    """
    expected = normalize_reference_text(transcript)
    if not expected:
        raise ValueError("voice reference transcript is empty")
    pcm = decode_reference_pcm16(audio_path)
    result = speech_runtime.transcribe(pcm, 16000)
    actual = str(result.get("text", ""))
    cer = character_error_rate(transcript, actual)
    if not result.get("speech_detected") or not normalize_reference_text(actual) or cer > max_cer:
        raise RuntimeError(f"voice_reference_transcript_mismatch: cer={cer:.4f}")
    return {
        "status": "ready",
        "cer": round(cer, 4),
        "reference_chars": len(expected),
        "recognized_chars": len(normalize_reference_text(actual)),
    }
