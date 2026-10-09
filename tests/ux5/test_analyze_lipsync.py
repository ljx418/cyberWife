import numpy as np

from tests.ux5.analyze_lipsync import (
    max_consecutive_voiced_freeze,
    mouth_motion_pass,
    post_speech_metrics,
)


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


def test_post_speech_gate_detects_a_moving_mouth_during_tail_silence() -> None:
    energy = np.concatenate((np.full(20, 0.05), np.zeros(20)))
    delta = np.concatenate((np.full(20, 8.0), np.full(20, 7.0)))
    second = np.concatenate((np.full(18, 1.0), np.full(20, 1.2)))
    report = post_speech_metrics(energy, delta, second, fps=25)
    assert report["evaluable"] is True
    assert report["mouth_delta_ratio"] > 0.78
    assert report["second_order_ratio"] > 1.0


def test_post_speech_gate_accepts_stable_idle_tail() -> None:
    energy = np.concatenate((np.full(20, 0.05), np.zeros(20)))
    delta = np.concatenate((np.full(20, 8.0), np.full(20, 3.0)))
    second = np.concatenate((np.full(18, 1.0), np.full(20, 0.4)))
    report = post_speech_metrics(energy, delta, second, fps=25)
    assert report["evaluable"] is True
    assert report["mouth_delta_ratio"] <= 0.78
    assert report["second_order_ratio"] <= 1.0


def test_freeze_gate_ignores_closed_idle_but_rejects_voiced_freeze() -> None:
    energy = np.concatenate((np.full(5, 0.05), np.zeros(5)))
    stable_tail = np.asarray([0.4, 0.4, 0.4, 0.4, 0.4, 0.0, 0.0, 0.0, 0.0])
    assert max_consecutive_voiced_freeze(energy, stable_tail) == 0

    frozen_voice = np.asarray([0.4, 0.0, 0.0, 0.0, 0.4, 0.4, 0.4, 0.4, 0.4])
    assert max_consecutive_voiced_freeze(energy, frozen_voice) == 3
