#!/usr/bin/env python3
"""Build intro, half-body idle, outro and a joined review sequence."""

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
from ops.fullscene_idle_pipeline import _stretch_first_last_loop
from ops.make_seamless_idle import encode, mean_absolute_error, read_frames


ROOT = Path(__file__).resolve().parents[1]
TRANSITION_WORKFLOW = ROOT / "ops/comfy_avatar_scene_transition_api.json"
IDLE_WORKFLOW = ROOT / "ops/comfy_avatar_halfbody_idle_api.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _crossfade(left: list[np.ndarray], right: list[np.ndarray], count: int = 12):
    if len(left) <= count or len(right) <= count:
        raise ValueError("clips are too short for crossfade")
    mixed = list(left[:-count])
    for index in range(count):
        weight = (index + 1) / (count + 1)
        frame = left[-count + index].astype(np.float32) * (1.0 - weight)
        frame += right[index].astype(np.float32) * weight
        mixed.append(np.clip(np.rint(frame), 0, 255).astype(np.uint8))
    mixed.extend(right[count:])
    return mixed


def _validate_video(path: Path, expected_frames: int) -> dict:
    frames, fps = read_frames(path)
    black = sum(float(frame.mean()) < 2.0 for frame in frames)
    diffs = [mean_absolute_error(frames[index - 1], frames[index]) for index in range(1, len(frames))]
    result = {
        "path": str(path),
        "sha256": _sha256(path),
        "frames": len(frames),
        "fps": round(fps, 3),
        "black_frames": black,
        "consecutive_mae_max": round(max(diffs), 4),
        "consecutive_mae_p95": round(float(np.percentile(diffs, 95)), 4),
        "first_last_mae": round(mean_absolute_error(frames[0], frames[-1]), 4),
    }
    if len(frames) != expected_frames or black or abs(fps - 16.0) > 0.1:
        raise RuntimeError(f"video_validation_failed:{result}")
    return result


def run(seated_keyframe: Path, close_keyframe: Path, output_dir: Path) -> dict:
    for source in (seated_keyframe, close_keyframe):
        if not source.is_file():
            raise FileNotFoundError(source)
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
            seated_keyframe.read_bytes()
            + close_keyframe.read_bytes()
            + TRANSITION_WORKFLOW.read_bytes()
            + IDLE_WORKFLOW.read_bytes()
        ).hexdigest()[:16]
        comfy_user = COMFY_ROOT / "user" / "cyberwife-runtime" / f"sequence-{digest}"
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

        start_input = COMFY_ROOT / "input" / f"cw_sequence_{digest}_seated.png"
        close_input = COMFY_ROOT / "input" / f"cw_sequence_{digest}_close.png"
        shutil.copy2(seated_keyframe, start_input)
        shutil.copy2(close_keyframe, close_input)
        copied_inputs.extend((start_input, close_input))

        transition = json.loads(TRANSITION_WORKFLOW.read_text(encoding="utf-8"))
        transition["1"]["inputs"]["image"] = start_input.name
        transition["18"]["inputs"]["image"] = close_input.name
        transition["17"]["inputs"]["filename_prefix"] = f"video/cyberWife/sequence/{digest}_intro"
        intro_source = _comfy_output(_submit(transition)[0])
        intro = output_dir / "intro-walk-to-camera.mp4"
        shutil.copy2(intro_source, intro)
        intro_frames, _ = read_frames(intro)

        outro = output_dir / "outro-walk-back-and-sit.mp4"
        encode(list(reversed(intro_frames)), outro, fps=16)

        idle_graph = json.loads(IDLE_WORKFLOW.read_text(encoding="utf-8"))
        idle_graph["1"]["inputs"]["image"] = close_input.name
        idle_graph["17"]["inputs"]["filename_prefix"] = f"video/cyberWife/sequence/{digest}_idle"
        idle_source = _comfy_output(_submit(idle_graph)[0])
        idle_source_copy = output_dir / "idle-halfbody-source-5s.mp4"
        shutil.copy2(idle_source, idle_source_copy)
        idle_source_frames, _ = read_frames(idle_source_copy)
        idle_frames = _stretch_first_last_loop(idle_source_frames)
        idle = output_dir / "idle-halfbody-10s.mp4"
        encode(idle_frames, idle, fps=16)

        combined_frames = _crossfade(intro_frames, idle_frames, 12)
        combined_frames = _crossfade(combined_frames, list(reversed(intro_frames)), 12)
        combined = output_dir / "review-intro-idle-outro.mp4"
        encode(combined_frames, combined, fps=16)

        manifest = {
            "schema_version": 1,
            "generation_mode": "direct_complete_scene_sequence",
            "matting": False,
            "seated_keyframe": {"path": str(seated_keyframe), "sha256": _sha256(seated_keyframe)},
            "close_keyframe": {"path": str(close_keyframe), "sha256": _sha256(close_keyframe)},
            "transition_workflow_sha256": _sha256(TRANSITION_WORKFLOW),
            "idle_workflow_sha256": _sha256(IDLE_WORKFLOW),
            "intro": _validate_video(intro, 81),
            "idle": _validate_video(idle, 160),
            "outro": _validate_video(outro, 81),
            "combined": _validate_video(combined, 298),
            "idle_motion": "one_soft_blink_and_shallow_breathing_only",
            "outro_construction": "exact_temporal_reverse_of_intro",
            "combined_crossfade_frames": 12,
        }
        if manifest["idle"]["first_last_mae"] > 3.0:
            raise RuntimeError(f"idle_loop_validation_failed:{manifest['idle']}")
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
        errors = []
        for component in reversed(stopped):
            try:
                _launcher("start", component)
            except Exception as exc:
                errors.append(f"{component}:{exc}")
        if errors:
            raise RuntimeError("runtime_restore_failed:" + ",".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seated-keyframe", required=True, type=Path)
    parser.add_argument("--close-keyframe", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.seated_keyframe, args.close_keyframe, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
