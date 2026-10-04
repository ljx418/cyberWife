import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_idle_workflow_is_reproducible_and_portrait_agnostic():
    workflow = json.loads((ROOT / "ops/comfy_avatar_idle_api.json").read_text(encoding="utf-8"))

    latent = workflow["12"]["inputs"]
    first_sampler = workflow["13"]["inputs"]
    second_sampler = workflow["14"]["inputs"]
    prompt = workflow["10"]["inputs"]["text"]

    assert (latent["width"], latent["height"], latent["length"]) == (512, 768, 81)
    assert first_sampler["noise_seed"] == second_sampler["noise_seed"] == 42
    assert "preserve the exact first-frame identity" in prompt
    assert "expression is locked" in prompt
    assert "one slow natural blink" in prompt
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
