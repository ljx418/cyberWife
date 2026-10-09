#!/usr/bin/env python3
"""Generate low-motion complete-scene Idle videos for one approved appearance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops.fullscene_idle_pipeline import run
from ops.scene_keyframe_pipeline import SCENE_DIRECTIONS


def prompts(label: str) -> dict[str, str]:
    return {
        slug: (
            "Photorealistic complete scene with the exact same adult woman, face, front-facing seated pose, "
            f"{label}, jewelry, room, furniture, contact shadows, ambient lighting and 16:9 framing in every "
            "frame; locked tripod camera; her head, shoulders, hands and torso remain at the initial coordinates; "
            "lips remain softly closed; the only actions are one natural soft blink and barely visible shallow "
            "breathing; background, furniture, curtains, plants, rain, fire and sunlight remain visually static. "
            + direction
        )
        for slug, direction in SCENE_DIRECTIONS.items()
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyframe-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--appearance-label", required=True)
    args = parser.parse_args()
    prompt_map = prompts(args.appearance_label)
    keyframes = {slug: args.keyframe_dir / f"{slug}.png" for slug in prompt_map}
    manifest = run(keyframes, args.output_dir, prompts=prompt_map)
    manifest["appearance_label"] = args.appearance_label
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
