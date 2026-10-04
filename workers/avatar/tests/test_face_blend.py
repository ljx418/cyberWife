import numpy as np

from utils.image import blend_lower_face


def test_lower_face_blend_preserves_glasses_region_and_feathers_edges():
    original = np.zeros((100, 80, 3), dtype=np.uint8)
    generated = np.full_like(original, 255)
    result = blend_lower_face(original, generated)

    assert np.max(result[:30]) == 0
    assert np.mean(result[70:90, 20:60]) > 240
    assert 0 < int(result[60, 0, 0]) < int(result[60, 20, 0])


def test_lower_face_blend_rejects_mismatched_shapes():
    original = np.zeros((10, 10, 3), dtype=np.uint8)
    generated = np.zeros((8, 10, 3), dtype=np.uint8)
    try:
        blend_lower_face(original, generated)
    except ValueError as exc:
        assert "identical" in str(exc)
    else:
        raise AssertionError("shape mismatch must be rejected")
