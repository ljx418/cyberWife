#!/usr/bin/env python3
"""Generate complete-scene full-body idle variants without person matting."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from ops.avatar_idle_pipeline import (
    COMFY_PYTHON,
    COMFY_ROOT,
    _component_ready,
    _comfy_output,
    _launcher,
    _stop_comfy,
    _submit,
    _wait_comfy,
    _windows_path,
)
from ops.make_seamless_idle import encode, mean_absolute_error, read_frames


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "ops/comfy_avatar_fullscene_idle_api.json"

NEGATIVE = (
    "talking, speech, phoneme, lip movement, mouth corner movement, open mouth, teeth, "
    "exaggerated expression, repeated blinking, rapid blinking, large gesture, pose change, "
    "arm lift, hand lift, waving, reaching, shoulder lift, head turn, head tilt, body sway, weight shift, "
    "standing up, sitting down, walking, sliding, floating body, foot movement, hand deformation, "
    "extra fingers, extra limbs, identity drift, clothing change, face distortion, body distortion, "
    "furniture deformation, cushion deformation drift, background motion, curtain motion, plant motion, "
    "city light flicker, lighting change, exposure change, camera shake, pan, tilt, zoom, crop change, "
    "cut, new person, text, watermark, blur, low quality"
)

POSE_PROMPTS = {
    "sofa-upright": (
        "photorealistic complete living-room scene with the exact same seated woman, preserve her exact "
        "identity, upright sofa pose, crossed ankles, hands resting on lap, clothing, furniture, cushion "
        "compression, contact shadows, warm lamp light, cool window fill, room geometry and 16:9 framing "
        "in every frame; locked tripod camera; she remains frozen in the initial seated pose and keeps "
        "gentle eye contact; both hands remain together at the exact initial coordinates on her lap, both "
        "feet remain planted at the exact initial coordinates, shoulders and head remain fixed; the only "
        "actions are one natural soft blink and barely visible shallow breathing; background and all "
        "furniture remain perfectly static"
    ),
    "sofa-relaxed": (
        "photorealistic complete living-room scene with the exact same woman relaxed against the sofa, "
        "preserve her exact identity, leaning pose, arm on cushion, crossed ankles, clothing, sofa occlusion, "
        "cushion compression, contact shadows, room geometry, lighting and 16:9 framing in every frame; "
        "locked tripod camera; she remains frozen in the initial pose; her right forearm and right hand "
        "remain continuously touching the same sofa cushion at the exact initial coordinates, her left hand "
        "stays on her lap, ankles remain crossed at the exact initial coordinates, shoulders and head remain "
        "fixed; the only actions are one natural soft blink and barely visible shallow breathing; background "
        "and all furniture remain perfectly static"
    ),
    "window-standing": (
        "photorealistic complete living-room scene with the exact same full-body woman standing by the "
        "window, preserve her exact identity, hairstyle, clothes, joined hands, foot positions, warm rim "
        "light, cool window fill, floor contact shadow, room geometry and 16:9 framing in every frame; "
        "locked tripod camera; she remains frozen in the initial standing pose; both feet stay planted at "
        "the exact initial coordinates, hands stay joined at the exact initial coordinates, shoulders, torso "
        "and head remain fixed; the only actions are one natural soft blink and barely visible shallow "
        "breathing; background, curtains, plants, city and all furniture remain perfectly static"
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stretch_first_last_loop(frames):
    """Stretch one first/last-constrained cycle to 160 frames without a midpoint join."""
    if len(frames) != 81:
        raise ValueError("first/last loop requires exactly 81 source frames")
    output = []
    for position in np.linspace(0.0, 80.0, 160):
        lower = int(np.floor(position))
        upper = min(lower + 1, 80)
        weight = position - lower
        blended = (
            frames[lower].astype(np.float32) * (1.0 - weight)
            + frames[upper].astype(np.float32) * weight
        )
        output.append(np.clip(np.rint(blended), 0, 255).astype(np.uint8))
    # Model conditioning returns to the requested composition semantically, but
    # VAE reconstruction can still leave a visible pixel seam. Converge the
    # complete frame (person, furniture and light together) over the last second.
    fade_frames = 16
    first = output[0].astype(np.float32)
    for index in range(len(output) - fade_frames, len(output)):
        linear = (index - (len(output) - fade_frames)) / (fade_frames - 1)
        weight = linear * linear * (3.0 - 2.0 * linear)
        blended = output[index].astype(np.float32) * (1.0 - weight) + first * weight
        output[index] = np.clip(np.rint(blended), 0, 255).astype(np.uint8)
    return output


def run(keyframes: dict[str, Path], output_dir: Path) -> dict:
    if not keyframes or not set(keyframes).issubset(POSE_PROMPTS):
        raise ValueError("one or more approved pose keyframes are required")
    output_dir.mkdir(parents=True, exist_ok=True)
    stopped: list[str] = []
    process: subprocess.Popen | None = None
    log_stream = None
    copied_inputs: list[Path] = []
    try:
        for component in ("avatar", "speech", "llama"):
            if _component_ready(component):
                _launcher("stop", component)
                stopped.append(component)
        digest = hashlib.sha256(
            b"".join(path.read_bytes() for _, path in sorted(keyframes.items()))
            + WORKFLOW.read_bytes()
        ).hexdigest()[:16]
        comfy_user = COMFY_ROOT / "user" / "cyberwife-runtime" / f"fullscene-{digest}"
        manager_dir = comfy_user / "__manager"
        manager_dir.mkdir(parents=True, exist_ok=True)
        (manager_dir / "config.ini").write_text(
            "[default]\nnetwork_mode = offline\ndb_mode = cache\n", encoding="utf-8"
        )
        log_stream = (output_dir / "comfyui.log").open("ab")
        process = subprocess.Popen(
            [
                str(COMFY_PYTHON), "-s", _windows_path(COMFY_ROOT / "main.py"),
                "--windows-standalone-build", "--listen", "127.0.0.1", "--port", "8188",
                "--disable-auto-launch", "--user-directory", _windows_path(comfy_user),
            ],
            cwd=COMFY_ROOT,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
        )
        _wait_comfy(process)
        records = {}
        for index, (pose, source) in enumerate(sorted(keyframes.items())):
            if not source.is_file():
                raise FileNotFoundError(source)
            input_path = COMFY_ROOT / "input" / f"cw_fullscene_{digest}_{pose}.png"
            shutil.copy2(source, input_path)
            copied_inputs.append(input_path)
            graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
            graph["1"]["inputs"]["image"] = input_path.name
            graph["10"]["inputs"]["text"] = POSE_PROMPTS[pose]
            graph["11"]["inputs"]["text"] = NEGATIVE
            seed = 104729 + index * 1009
            graph["13"]["inputs"]["noise_seed"] = seed
            graph["14"]["inputs"]["noise_seed"] = seed
            graph["17"]["inputs"]["filename_prefix"] = f"video/cyberWife/fullscene/{digest}_{pose}"
            source_video = _comfy_output(_submit(graph)[0])
            source_copy = output_dir / f"{pose}-source-5s.mp4"
            shutil.copy2(source_video, source_copy)
            frames, source_fps = read_frames(source_copy)
            loop = _stretch_first_last_loop(frames)
            target = output_dir / f"{pose}-idle-10s.mp4"
            encode(loop, target, fps=16)
            decoded, fps = read_frames(target)
            black_frames = sum(float(frame.mean()) < 2.0 for frame in decoded)
            record = {
                "pose": pose,
                "keyframe": str(source),
                "keyframe_sha256": _sha256(source),
                "seed": seed,
                "source_frames": len(frames),
                "source_fps": round(source_fps, 3),
                "output": str(target),
                "output_sha256": _sha256(target),
                "output_frames": len(decoded),
                "output_fps": round(fps, 3),
                "first_last_mae": round(mean_absolute_error(decoded[0], decoded[-1]), 4),
                "midpoint_mae": round(mean_absolute_error(decoded[79], decoded[80]), 4),
                "black_frames": black_frames,
                "construction": "complete_scene_first_last_conditioned_timescale_2x",
                "matting": False,
            }
            if len(decoded) != 160 or black_frames or record["first_last_mae"] > 3.0:
                raise RuntimeError(f"fullscene_validation_failed:{pose}:{record}")
            records[pose] = record
        manifest = {
            "schema_version": 1,
            "workflow_sha256": _sha256(WORKFLOW),
            "generation_mode": "direct_complete_scene",
            "matting": False,
            "records": records,
        }
        (output_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return manifest
    finally:
        _stop_comfy(process)
        if log_stream is not None:
            log_stream.close()
        for path in copied_inputs:
            path.unlink(missing_ok=True)
        restore_errors = []
        for component in reversed(stopped):
            try:
                _launcher("start", component)
            except Exception as exc:
                restore_errors.append(f"{component}:{exc}")
        if restore_errors:
            raise RuntimeError("runtime_restore_failed:" + ",".join(restore_errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyframe-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--pose", action="append", choices=sorted(POSE_PROMPTS))
    args = parser.parse_args()
    poses = args.pose or list(POSE_PROMPTS)
    keyframes = {
        pose: args.keyframe_dir / f"keyframe-{pose}.png" for pose in poses
    }
    print(json.dumps(run(keyframes, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
