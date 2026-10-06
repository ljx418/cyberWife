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


def test_flush_returns_to_short_idle_wait() -> None:
    asr = _asr()
    asr.put_audio_frame(np.zeros(asr.chunk, dtype=np.float32), {})
    asr.flush_talk()
    assert asr._audio_queue_timeout(10_000.0) == 0.01
