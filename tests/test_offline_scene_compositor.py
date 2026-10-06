from pathlib import Path

import cv2
import numpy as np

from ops.offline_scene_compositor import _cover, whole_person_mattes


def test_cover_returns_requested_size() -> None:
    image = np.zeros((90, 160, 3), dtype=np.uint8)
    assert _cover(image, 50, 80).shape == (80, 50, 3)


def test_whole_person_matte_preserves_central_subject() -> None:
    background = np.full((192, 128, 3), (204, 211, 216), dtype=np.uint8)
    frames = []
    for offset in (0, 1, 0):
        frame = background.copy()
        cv2.ellipse(frame, (64 + offset, 68), (25, 38), 0, 0, 360, (35, 45, 60), -1)
        cv2.rectangle(frame, (25 + offset, 94), (103 + offset, 191), (30, 35, 180), -1)
        frames.append(frame)
    mattes = whole_person_mattes(frames)
    assert len(mattes) == 3
    assert all(float(mask[80, 64]) > 0.9 for mask in mattes)
    assert all(float(mask[10, 10]) < 0.1 for mask in mattes)
    areas = [float(np.mean(mask > 0.5)) for mask in mattes]
    assert max(areas) - min(areas) < 0.02
