import numpy as np

from ops.build_video_avatar import _letterbox, _smooth


def test_letterbox_preserves_portrait_without_stretching():
    source = np.zeros((960, 768, 3), dtype=np.uint8)
    result = _letterbox(source)
    assert result.shape == (768, 512, 3)


def test_face_box_smoothing_rejects_single_frame_jitter_in_output():
    boxes = np.asarray([[100, 300, 80, 260], [102, 302, 81, 261], [170, 370, 140, 320], [104, 304, 82, 262]])
    smoothed = _smooth(boxes, radius=2)
    assert smoothed[2, 0] < 170
    assert smoothed.dtype == np.int32
