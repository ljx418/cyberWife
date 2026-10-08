from __future__ import annotations

import inspect
import json
from pathlib import Path

from ops import multi_scene_idle_pipeline, scene_keyframe_pipeline


ROOT = Path(__file__).resolve().parents[3]


def test_scene_keyframe_workflow_is_local_two_reference_complete_scene():
    workflow = json.loads(
        (ROOT / "ops/comfy_avatar_scene_keyframe_api.json").read_text(encoding="utf-8")
    )
    assert workflow["6"]["inputs"]["images.image_1"] == ["1", 0]
    assert workflow["6"]["inputs"]["images.image_2"] == ["2", 0]
    assert workflow["8"]["inputs"] == {"width": 1536, "height": 864, "batch_size": 1}
    assert workflow["3"]["inputs"]["unet_name"] == "qwen-image-2.1-Q6_K.gguf"
    assert workflow["9"]["inputs"]["steps"] == 25


def test_scene_contract_has_exactly_three_missing_scenes_and_no_matting():
    expected = {"morning-bedroom", "rainy-library", "garden-sunroom"}
    assert set(scene_keyframe_pipeline.SCENE_DIRECTIONS) == expected
    assert set(multi_scene_idle_pipeline.PROMPTS) == expected
    source = inspect.getsource(scene_keyframe_pipeline.run)
    assert '"generation_mode": "local_qwen21_direct_complete_scene"' in source
    assert '"matting": False' in source
    assert "remove_background" not in source
    assert "alpha" not in source


def test_prompts_freeze_mouth_camera_and_background():
    for prompt in multi_scene_idle_pipeline.PROMPTS.values():
        normalized = prompt.lower()
        assert "locked tripod camera" in normalized
        assert "lips remain softly closed" in normalized
        assert "background" in normalized and "static" in normalized


def test_composition_normalization_is_complete_frame_not_person_matting():
    source = inspect.getsource(scene_keyframe_pipeline._normalize_composition)
    assert "crop_width * 9 / 16" in source
    assert "cv2.resize(cropped, (1536, 864)" in source
    assert "mask" not in source
    assert "alpha" not in source
