import numpy as np

from ops.build_video_avatar import AVATAR_BUILD_REVISION, WAV2LIP_FACE_SIZE, _letterbox, _loop_metrics, _smooth, _wav2lip_box
from ops.make_seamless_idle import palindrome_frames


def test_letterbox_preserves_portrait_without_stretching():
    source = np.zeros((960, 768, 3), dtype=np.uint8)
    result = _letterbox(source)
    assert result.shape == (768, 512, 3)


def test_face_box_smoothing_rejects_single_frame_jitter_in_output():
    boxes = np.asarray([[100, 300, 80, 260], [102, 302, 81, 261], [170, 370, 140, 320], [104, 304, 82, 262]])
    smoothed = _smooth(boxes, radius=2)
    assert smoothed[2, 0] < 170
    assert smoothed.dtype == np.int32


def test_wav2lip_box_matches_bundled_generator_padding():
    assert _wav2lip_box((163, 205, 374, 464)) == [205, 474, 163, 374]


def test_wav2lip_box_is_bounded_at_frame_edge():
    assert _wav2lip_box((-20, -30, 140, 190)) == [0, 200, 0, 140]


def test_wav2lip_builder_matches_bundled_high_resolution_checkpoint():
    assert WAV2LIP_FACE_SIZE == 256
    assert AVATAR_BUILD_REVISION == "cropv2"


def test_palindrome_loop_has_exact_seam_and_turnaround():
    source = [np.full((4, 4, 3), value, dtype=np.uint8) for value in range(80)]
    frames = palindrome_frames(source)

    assert len(frames) == 160
    assert np.array_equal(frames[0], frames[-1])
    assert np.array_equal(frames[79], frames[80])
    metrics = _loop_metrics(frames)
    assert metrics["mode"] == "closed_palindrome"
    assert metrics["first_last_mae"] == 0.0
    assert metrics["turnaround_mae"] == 0.0
    assert metrics["palindrome_mae"] == 0.0


def test_non_palindrome_is_kept_on_legacy_ping_pong_mode():
    frames = [np.full((4, 4, 3), value, dtype=np.uint8) for value in range(80)]
    metrics = _loop_metrics(frames)

    assert metrics["mode"] == "ping_pong"
    assert metrics["first_last_mae"] > 3.0
