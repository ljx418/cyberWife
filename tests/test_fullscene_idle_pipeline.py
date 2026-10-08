import inspect
import json
from pathlib import Path

import numpy as np

from ops import fullscene_idle_pipeline


ROOT = Path(__file__).resolve().parents[1]


def test_fullscene_workflow_preserves_complete_scene_geometry():
    workflow = json.loads(
        (ROOT / "ops/comfy_avatar_fullscene_idle_api.json").read_text(encoding="utf-8")
    )

    latent = workflow["12"]["inputs"]
    positive = workflow["10"]["inputs"]["text"]
    negative = workflow["11"]["inputs"]["text"]

    assert (latent["width"], latent["height"], latent["length"]) == (768, 432, 81)
    assert workflow["13"]["inputs"]["noise_seed"] == 104729
    assert workflow["14"]["inputs"]["noise_seed"] == 104729
    assert workflow["16"]["inputs"]["fps"] == 16.0
    assert workflow["12"]["class_type"] == "WanFirstLastFrameToVideo"
    assert workflow["12"]["inputs"]["start_image"] == ["1", 0]
    assert workflow["12"]["inputs"]["end_image"] == ["1", 0]
    assert "complete scene" in positive.lower()
    assert "contact shadow" in positive.lower()
    assert "background motion" in negative.lower()
    assert "lighting change" in negative.lower()


def test_fullscene_pipeline_has_three_pose_contract_and_no_matting_stage():
    assert set(fullscene_idle_pipeline.POSE_PROMPTS) == {
        "sofa-upright",
        "sofa-relaxed",
        "window-standing",
    }
    source = inspect.getsource(fullscene_idle_pipeline.run)
    assert '"generation_mode": "direct_complete_scene"' in source
    assert '"matting": False' in source
    assert "remove_background" not in source
    assert "alpha" not in source


def test_first_last_cycle_stretches_without_midpoint_join_or_reversal():
    frames = [np.full((2, 2, 3), index, dtype=np.uint8) for index in range(81)]
    frames[-1] = frames[0]
    loop = fullscene_idle_pipeline._stretch_first_last_loop(frames)

    assert len(loop) == 160
    assert np.array_equal(loop[0], loop[-1])
    assert int(loop[40][0, 0, 0]) in {20, 21}
    assert int(loop[80][0, 0, 0]) in {40, 41}
    assert np.array_equal(loop[0], loop[-1])
    assert int(loop[-2][0, 0, 0]) <= 2


def test_idle_motion_gate_accepts_small_complete_frame_motion(monkeypatch, tmp_path):
    detector = tmp_path / "det.onnx"
    detector.write_bytes(b"offline")
    detections = iter([
        [(100 + offset, 80, 300 + offset, 320, 0.99)]
        for offset in (0, 1, -1, 1, 0)
    ])
    monkeypatch.setattr(
        fullscene_idle_pipeline,
        "detect_faces",
        lambda _frame, _model: next(detections),
    )
    frames = [np.zeros((432, 768, 3), dtype=np.uint8) for _ in range(5)]

    metrics = fullscene_idle_pipeline._validate_idle_motion(
        frames, model_path=detector
    )

    assert metrics["face_center_p95_percent_diagonal"] < 1
    assert metrics["face_area_cv_percent"] == 0


def test_idle_motion_gate_rejects_large_face_translation(monkeypatch, tmp_path):
    detector = tmp_path / "det.onnx"
    detector.write_bytes(b"offline")
    detections = iter([
        [(x, 80, x + 200, 320, 0.99)] for x in (40, 80, 120, 160, 200)
    ])
    monkeypatch.setattr(
        fullscene_idle_pipeline,
        "detect_faces",
        lambda _frame, _model: next(detections),
    )
    frames = [np.zeros((432, 768, 3), dtype=np.uint8) for _ in range(5)]

    with np.testing.assert_raises_regex(RuntimeError, "idle_motion_validation_failed"):
        fullscene_idle_pipeline._validate_idle_motion(frames, model_path=detector)
