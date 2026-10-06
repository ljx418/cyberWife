from tests.ux5.analyze_lipsync import mouth_motion_pass


def test_mouth_motion_gate_accepts_responsive_non_frozen_video() -> None:
    report = {
        "gates": {
            "mouth_responds_during_voice": True,
            "no_black_frames": True,
            "no_frozen_frames": True,
        }
    }

    assert mouth_motion_pass(report) is True


def test_mouth_motion_gate_rejects_static_mouth_even_when_video_is_live() -> None:
    report = {
        "gates": {
            "mouth_responds_during_voice": False,
            "no_black_frames": True,
            "no_frozen_frames": True,
        }
    }

    assert mouth_motion_pass(report) is False


def test_mouth_motion_gate_rejects_frozen_or_black_output() -> None:
    frozen = {
        "gates": {
            "mouth_responds_during_voice": True,
            "no_black_frames": True,
            "no_frozen_frames": False,
        }
    }
    black = {
        "gates": {
            "mouth_responds_during_voice": True,
            "no_black_frames": False,
            "no_frozen_frames": True,
        }
    }

    assert mouth_motion_pass(frozen) is False
    assert mouth_motion_pass(black) is False
