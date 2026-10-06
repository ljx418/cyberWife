import inspect
import json
from pathlib import Path

import numpy as np

from ops import scene_sequence_pipeline


ROOT = Path(__file__).resolve().parents[1]


def test_transition_workflow_has_distinct_first_last_frames():
    graph = json.loads(
        (ROOT / "ops/comfy_avatar_scene_transition_api.json").read_text(encoding="utf-8")
    )
    assert graph["12"]["class_type"] == "WanFirstLastFrameToVideo"
    assert graph["12"]["inputs"]["start_image"] == ["1", 0]
    assert graph["12"]["inputs"]["end_image"] == ["18", 0]
    assert (graph["12"]["inputs"]["width"], graph["12"]["inputs"]["height"]) == (768, 432)
    assert "walk" in graph["10"]["inputs"]["text"].lower()
    assert "teleport" in graph["11"]["inputs"]["text"].lower()


def test_halfbody_idle_locks_expression_and_camera():
    graph = json.loads(
        (ROOT / "ops/comfy_avatar_halfbody_idle_api.json").read_text(encoding="utf-8")
    )
    assert graph["12"]["inputs"]["start_image"] == graph["12"]["inputs"]["end_image"]
    assert "waist-up" in graph["10"]["inputs"]["text"]
    assert "one soft natural blink" in graph["10"]["inputs"]["text"]
    assert "strict frontal" in graph["10"]["inputs"]["text"]
    assert "nose bridge and chin centered" in graph["10"]["inputs"]["text"]
    assert "both eyes level and equally visible" in graph["10"]["inputs"]["text"]
    assert "zero head yaw pitch and roll" in graph["10"]["inputs"]["text"]
    assert "three-quarter view" in graph["11"]["inputs"]["text"]
    assert "looking aside" in graph["11"]["inputs"]["text"]
    assert "head turn" in graph["11"]["inputs"]["text"]
    assert "lip movement" in graph["11"]["inputs"]["text"]


def test_crossfade_preserves_length_and_pipeline_has_no_matting():
    left = [np.full((2, 2, 3), index, np.uint8) for index in range(20)]
    right = [np.full((2, 2, 3), 100 + index, np.uint8) for index in range(20)]
    joined = scene_sequence_pipeline._crossfade(left, right, 4)
    assert len(joined) == 36
    source = inspect.getsource(scene_sequence_pipeline.run)
    assert '"matting": False' in source
    assert "alpha" not in source.lower()
