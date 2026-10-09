from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from avatars.audio_features.base_asr import BaseASR


def _asr() -> BaseASR:
    return BaseASR(SimpleNamespace(fps=25, batch_size=4, l=10, r=10))


def test_recent_external_pcm_uses_jitter_tolerant_wait() -> None:
    asr = _asr()
    asr._last_external_audio_at = 100.0
    assert asr._audio_queue_timeout(100.02) >= 0.04
    assert asr._audio_queue_timeout(100.50) == 0.01


def test_external_pcm_is_not_reclassified_as_silence() -> None:
    asr = _asr()
    payload = np.full(asr.chunk, 0.125, dtype=np.float32)
    asr.put_audio_frame(payload, {"clock_ms": 0, "generation": 7})

    frame = asr.get_audio_frame()

    assert frame.type == 0
    assert frame.userdata == {"clock_ms": 0, "generation": 7}
    np.testing.assert_array_equal(frame.data, payload)


def test_sustained_external_silence_releases_to_idle_after_bounded_hangover() -> None:
    asr = _asr()
    asr.put_audio_frame(np.full(asr.chunk, 0.125, dtype=np.float32), {})
    assert asr.get_audio_frame().type == 0

    observed = []
    for _ in range(asr._external_silence_release_frames):
        asr.put_audio_frame(np.zeros(asr.chunk, dtype=np.float32), {})
        observed.append(asr.get_audio_frame().type)

    assert observed[:-1] == [0] * (asr._external_silence_release_frames - 1)
    assert observed[-1] == 1


def test_complete_audio_appends_silent_drain_without_discarding_queued_speech() -> None:
    asr = _asr()
    payload = np.full(asr.chunk, 0.125, dtype=np.float32)
    asr.put_audio_frame(payload, {"generation": 9})
    asr.complete_audio(9)

    first = asr.get_audio_frame()
    assert first.type == 0
    np.testing.assert_array_equal(first.data, payload)
    drain = [asr.get_audio_frame() for _ in range(asr.batch_size * 2)]
    assert all(frame.type == 1 for frame in drain)
    assert all(frame.userdata == {"generation": 9, "complete": True} for frame in drain)


def test_stale_or_duplicate_generation_completion_is_rejected() -> None:
    asr = _asr()
    payload = np.full(asr.chunk, 0.125, dtype=np.float32)
    assert asr.put_audio_frame(payload, {"generation": 10}) is True
    assert asr.complete_audio(9) is False
    assert asr.complete_audio(10) is True
    assert asr.complete_audio(10) is False
    assert asr.put_audio_frame(payload, {"generation": 9}) is False


def test_flush_returns_to_short_idle_wait() -> None:
    asr = _asr()
    asr.put_audio_frame(np.zeros(asr.chunk, dtype=np.float32), {})
    asr.flush_talk()
    assert asr._audio_queue_timeout(10_000.0) == 0.01
