from __future__ import annotations

import numpy as np
import pytest

from avatars.base_avatar import AudioFrameData, frame_speaking_mask


def frame(frame_type: int) -> AudioFrameData:
    return AudioFrameData(np.zeros(320, dtype=np.float32), type=frame_type)


def test_mixed_batch_keeps_video_frame_state_independent() -> None:
    audio = [
        frame(0), frame(0),
        frame(1), frame(1),
        frame(1), frame(0),
        frame(1), frame(1),
    ]
    assert frame_speaking_mask(audio) == [True, False, True, False]


def test_odd_audio_frame_count_fails_closed() -> None:
    with pytest.raises(ValueError, match="must be even"):
        frame_speaking_mask([frame(1)])
