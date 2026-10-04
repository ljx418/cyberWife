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
    assert "preserve the exact identity" in prompt
    assert "accessories" in prompt and "hand placement" in prompt
    assert "blue and white" not in prompt and "eyeglasses, hairstyle" not in prompt
    assert workflow["16"]["inputs"]["fps"] == 16.0
