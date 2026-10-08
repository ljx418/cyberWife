#!/usr/bin/env python3
"""Generate three low-motion complete-scene Idle candidates from approved keyframes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ops.fullscene_idle_pipeline import run
from ops.scene_keyframe_pipeline import SCENE_DIRECTIONS


PROMPTS = {
    slug: (
        "Photorealistic complete scene with the exact same woman, face, front-facing seated pose, red knit "
        "outfit, jewelry, room, furniture, contact shadows, ambient lighting and 16:9 framing in every frame; "
        "locked tripod camera; her head, shoulders, hands and torso remain at the initial coordinates; lips "
        "remain softly closed; the only actions are one natural soft blink and barely visible shallow breathing; "
        "background, furniture, curtains, plants, rain, fire and sunlight remain visually static. "
        + direction
    )
    for slug, direction in SCENE_DIRECTIONS.items()
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyframe-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    keyframes = {slug: args.keyframe_dir / f"{slug}.png" for slug in PROMPTS}
    print(json.dumps(run(keyframes, args.output_dir, prompts=PROMPTS), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
