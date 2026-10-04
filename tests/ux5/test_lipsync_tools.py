from __future__ import annotations

import numpy as np

from tests.ux5.analyze_lipsync import correlation_at_shift, mirror_index


def test_mirror_index_closed_cycle() -> None:
    assert [mirror_index(4, value) for value in range(10)] == [0, 1, 2, 3, 3, 2, 1, 0, 0, 1]


def test_relative_shift_finds_delayed_motion() -> None:
    audio = np.asarray([0, 0, 1, 3, 1, 0, 0, 2, 4, 2, 0, 0], dtype=float)
    motion = np.concatenate((np.zeros(2), audio[:-2]))
    scores = {shift: correlation_at_shift(audio, motion, shift) for shift in range(-3, 4)}
    assert max(scores, key=scores.get) == 2
