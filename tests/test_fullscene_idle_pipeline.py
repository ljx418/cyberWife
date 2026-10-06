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
