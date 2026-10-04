from types import SimpleNamespace

import numpy as np
from av.video.frame import PictureType

from streamout.h264_websocket import H264WebSocketOutput


class _RecordingCodec:
    def __init__(self):
        self.picture_types = []

    def encode(self, frame):
        self.picture_types.append(frame.pict_type)
        return []


def test_generation_change_forces_decoder_recovery_keyframe(monkeypatch):
    output = H264WebSocketOutput(SimpleNamespace(fps=25))
    codec = _RecordingCodec()
    output._codec = codec
    output._width = 4
    output._height = 4
    monkeypatch.setattr("streamout.h264_websocket.time.sleep", lambda _: None)
    frame = np.zeros((4, 4, 3), dtype=np.uint8)

    output.push_video_frame(frame, generation=1)
    output.push_video_frame(frame, generation=1)
    output.push_video_frame(frame, generation=2)
    output.push_video_frame(frame, generation=0)

    assert codec.picture_types[0] == PictureType.I
    assert codec.picture_types[1] != PictureType.I
    assert codec.picture_types[2] == PictureType.I
    assert codec.picture_types[3] != PictureType.I
    assert output._last_generation == 2
