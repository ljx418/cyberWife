import json
import inspect
from pathlib import Path

import numpy as np

from ops.avatar_idle_pipeline import _workflow_revision, run_pipeline
from ops.make_seamless_idle import palindrome_frames


ROOT = Path(__file__).resolve().parents[1]


def test_idle_workflow_is_reproducible_and_portrait_agnostic():
    workflow = json.loads((ROOT / "ops/comfy_avatar_idle_api.json").read_text(encoding="utf-8"))

    latent = workflow["12"]["inputs"]
    first_sampler = workflow["13"]["inputs"]
    second_sampler = workflow["14"]["inputs"]
    prompt = workflow["10"]["inputs"]["text"]

    assert (latent["width"], latent["height"], latent["length"]) == (512, 768, 81)
    assert first_sampler["noise_seed"] == second_sampler["noise_seed"] == 104729
    assert "preserve exact identity" in prompt
    assert "exact first-frame head pose" in prompt
    assert "barely perceptible continuous movement" in prompt
    assert "one natural soft blink" in prompt
    assert "blue and white" not in prompt and "eyeglasses, hairstyle" not in prompt
    assert workflow["16"]["inputs"]["fps"] == 16.0


def test_frontalization_workflow_standardizes_geometry_and_background():
    workflow = json.loads(
        (ROOT / "ops/comfy_avatar_frontalize_api.json").read_text(encoding="utf-8")
    )

    prompt = workflow["5"]["inputs"]["prompt"]
    negative = workflow["5"]["inputs"]["negative_prompt"]
    latent = workflow["7"]["inputs"]

    assert workflow["2"]["inputs"]["unet_name"] == "qwen-image-2.1-Q6_K.gguf"
    assert (latent["width"], latent["height"]) == (768, 1152)
    assert workflow["8"]["inputs"]["seed"] == 314159
    assert "exactly the same person" in prompt
    assert "#D8D3CC" in prompt and "no furniture" in prompt
    assert "side profile" in negative and "hand" in negative


def test_idle_checkpoint_revision_binds_both_workflows():
    revision = _workflow_revision()
    assert len(revision) == 64
    assert revision == _workflow_revision()


def test_product_pipeline_preserves_complete_generated_frames():
    frames = [np.full((12, 8, 3), index, dtype=np.uint8) for index in range(80)]
    loop = palindrome_frames(frames)
    assert len(loop) == 160
    assert np.array_equal(loop[0], loop[-1])
    assert np.array_equal(loop[37], frames[37])
    assert "localized_blink" not in inspect.getsource(run_pipeline)
