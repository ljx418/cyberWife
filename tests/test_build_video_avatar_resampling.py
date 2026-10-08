import numpy as np

from ops.build_video_avatar import _resample_frames_and_boxes


def test_resample_16fps_ten_seconds_to_250_runtime_frames():
    frames = [np.full((2, 2, 3), index, dtype=np.uint8) for index in range(160)]
    boxes = np.asarray([[index, index, index, index] for index in range(160)], dtype=np.float32)

    sampled, sampled_boxes = _resample_frames_and_boxes(frames, boxes, 16.0, 25.0)

    assert len(sampled) == 250
    assert sampled_boxes.shape == (250, 4)
    assert int(sampled[25][0, 0, 0]) == 16
    assert int(sampled[125][0, 0, 0]) == 80
    assert int(sampled[-1][0, 0, 0]) == 159


def test_resample_interpolates_between_adjacent_source_frames():
    frames = [np.full((2, 2, 3), value, dtype=np.uint8) for value in (0, 100)]
    boxes = np.asarray([[0, 0, 0, 0], [100, 100, 100, 100]], dtype=np.float32)

    sampled, sampled_boxes = _resample_frames_and_boxes(frames, boxes, 1.0, 2.0)

    assert [int(frame[0, 0, 0]) for frame in sampled] == [0, 50, 100, 100]
    assert sampled_boxes[:, 0].tolist() == [0, 50, 100, 100]
