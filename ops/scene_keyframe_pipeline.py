#!/usr/bin/env python3
"""Generate identity-preserving complete-scene keyframes on local ComfyUI."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import cv2

from ops.avatar_idle_pipeline import (
    COMFY_PYTHON,
    COMFY_ROOT,
    FACE_DETECTOR,
    _component_ready,
    _comfy_output,
    _launcher,
    _stop_comfy,
    _submit,
    _wait_comfy,
    _windows_path,
)
from ops.scrfd_detector import detect_faces


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / "ops/comfy_avatar_scene_keyframe_api.json"

SCENE_DIRECTIONS = {
    "morning-bedroom": "The woman sits naturally at the edge of the bed in the morning bedroom.",
    "rainy-library": "The woman sits naturally in the leather armchair in the rainy night library.",
    "garden-sunroom": "The woman sits naturally near the front of the sofa in the garden sunroom.",
}

PROMPT_BASE = (
    "Create one seamless photorealistic 16:9 complete-scene photograph. Use image 1 as the authoritative "
    "identity, face, black updo hairstyle, loose side strands, long gold sun earrings, necklace, red V-neck "
    "knit sweater and black lower garment reference. Use image 2 as the exact room, architecture, furniture "
    "layout and color reference. Preserve the exact adult woman and integrate her physically into the room "
    "with coherent perspective, furniture contact, occlusion, ambient light, cast shadow and color temperature. "
    "One person only. Locked eye-level tripod camera. Match the close half-body scale of image 1: crop at the "
    "waist, top of hair near 8 percent frame height, face at least 15 percent of frame width, shoulders spanning "
    "about half the frame. Centered front-facing head-and-torso framing, both eyes visible, level head and "
    "shoulders, direct eye contact, relaxed neutral expression, lips softly closed, face large and sharp enough "
    "for a native 256 pixel lip crop, safe margin around hair and shoulders. Do not zoom out to show the full body. "
    "Direct complete-scene generation, not a collage or cutout. "
)

ALTERNATE_APPEARANCE_PROMPT_BASE = (
    "Create one seamless photorealistic 16:9 complete-scene photograph. Use image 1 as the authoritative "
    "identity and facial reference for the exact same adult woman. Preserve her face shape, eyes, nose, lips, "
    "skin tone, black updo hairstyle with loose side strands, long gold sun earrings and necklace. Change only "
    "her clothing to a modest blue-and-white small floral blouse with natural woven fabric, long sleeves and a "
    "simple round neckline. Use image 2 as the exact room, architecture, furniture layout and color reference. "
    "Integrate her physically into the room with coherent perspective, furniture contact, occlusion, ambient "
    "light, cast shadow and color temperature. One person only. Locked eye-level tripod camera. Match the close "
    "half-body scale of image 1: crop at the waist, top of hair near 8 percent frame height, face at least 15 "
    "percent of frame width, shoulders spanning about half the frame. Centered front-facing head-and-torso "
    "framing. Her face must point exactly straight into the camera: zero yaw, zero pitch, zero roll, both ears "
    "equally visible, both eyes horizontal and equally sized, nose bridge exactly centered between the eyes, "
    "facial left and right sides symmetric. Both eyes visible, level head and shoulders, direct eye contact, relaxed neutral expression, lips "
    "softly closed, face large and sharp enough for a native 256 pixel lip crop, safe margin around hair and "
    "shoulders. Do not zoom out to show the full body. Direct complete-scene generation, not a collage or cutout. "
)

NEGATIVE = (
    "different person, identity drift, face change, age change, outfit change, jewelry change, side profile, "
    "three-quarter face, quarter profile, profile, face yaw, looking sideways, looking away, head tilt, closed eyes, open mouth, teeth, talking, smile, hand near face, "
    "extra person, duplicate person, extra limbs, malformed hands, floating body, collage, split screen, cutout, "
    "matte edge, transparent layer, mismatched light, beauty-filter skin, text, watermark, blurred face, low quality"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_keyframe(path: Path) -> dict:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("scene.keyframe_decode_failed")
    height, width = image.shape[:2]
    if (width, height) != (1536, 864):
        raise RuntimeError(f"scene.keyframe_size_invalid:{width}x{height}")
    faces = detect_faces(image, FACE_DETECTOR)
    if len(faces) != 1:
        raise RuntimeError(f"scene.keyframe_face_count:{len(faces)}")
    x1, y1, x2, y2, confidence = faces[0]
    face_width, face_height = x2 - x1, y2 - y1
    if face_width < 180 or face_height < 180:
        raise RuntimeError("scene.keyframe_face_too_small")
    sharpness = float(cv2.Laplacian(image[int(y1):int(y2), int(x1):int(x2)], cv2.CV_64F).var())
    if sharpness < 25:
        raise RuntimeError(f"scene.keyframe_face_blur:{sharpness:.3f}")
    return {
        "frame_size": [width, height],
        "face_box": [round(y1), round(y2), round(x1), round(x2)],
        "face_confidence": round(float(confidence), 5),
        "face_sharpness": round(sharpness, 3),
    }


def _normalize_composition(source: Path, target: Path, *, desired_face_width: int = 210) -> dict:
    """Crop the already-integrated complete frame; never isolate the person."""
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("scene.keyframe_decode_failed")
    height, width = image.shape[:2]
    faces = detect_faces(image, FACE_DETECTOR)
    if len(faces) != 1:
        raise RuntimeError(f"scene.keyframe_face_count:{len(faces)}")
    x1, y1, x2, y2, _ = faces[0]
    face_width = float(x2 - x1)
    scale = max(1.0, desired_face_width / max(1.0, face_width))
    crop_width = min(width, round(width / scale))
    crop_height = min(height, round(crop_width * 9 / 16))
    crop_width = min(width, round(crop_height * 16 / 9))
    face_center_x = (x1 + x2) / 2
    desired_face_top = crop_height * 0.10
    left = round(face_center_x - crop_width / 2)
    top = round(y1 - desired_face_top)
    left = max(0, min(width - crop_width, left))
    top = max(0, min(height - crop_height, top))
    cropped = image[top:top + crop_height, left:left + crop_width]
    normalized = cv2.resize(cropped, (1536, 864), interpolation=cv2.INTER_LANCZOS4)
    temporary = target.with_suffix(".tmp.png")
    if not cv2.imwrite(str(temporary), normalized):
        raise RuntimeError("scene.keyframe_write_failed")
    temporary.replace(target)
    return {
        "mode": "complete_frame_16_9_crop",
        "source_size": [width, height],
        "crop_box": [left, top, left + crop_width, top + crop_height],
        "scale": round(scale, 5),
    }


def run(
    identity: Path,
    backgrounds: dict[str, Path],
    output_dir: Path,
    *,
    prompt_base: str = PROMPT_BASE,
    appearance_id: str | None = None,
    appearance_label: str | None = None,
) -> dict:
    identity = Path(identity).resolve()
    output_dir = Path(output_dir).resolve()
    if not identity.is_file() or not backgrounds or set(backgrounds) != set(SCENE_DIRECTIONS):
        raise ValueError("scene.identity_or_backgrounds_invalid")
    output_dir.mkdir(parents=True, exist_ok=True)
    stopped: list[str] = []
    copied_inputs: list[Path] = []
    process: subprocess.Popen | None = None
    log_stream = None
    try:
        for component in ("avatar", "speech", "llama"):
            if _component_ready(component):
                _launcher("stop", component)
                stopped.append(component)
        digest = hashlib.sha256(identity.read_bytes() + WORKFLOW.read_bytes()).hexdigest()[:16]
        comfy_user = COMFY_ROOT / "user" / "cyberwife-runtime" / f"scene-keyframes-{digest}"
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
        identity_input = COMFY_ROOT / "input" / f"cw_scene_{digest}_identity.png"
        shutil.copy2(identity, identity_input)
        copied_inputs.append(identity_input)
        records: dict[str, dict] = {}
        for index, (slug, background) in enumerate(sorted(backgrounds.items())):
            background = Path(background).resolve()
            if not background.is_file():
                raise FileNotFoundError(background)
            background_input = COMFY_ROOT / "input" / f"cw_scene_{digest}_{slug}.webp"
            shutil.copy2(background, background_input)
            copied_inputs.append(background_input)
            graph = json.loads(WORKFLOW.read_text(encoding="utf-8"))
            graph["1"]["inputs"]["image"] = identity_input.name
            graph["2"]["inputs"]["image"] = background_input.name
            prompt = prompt_base + SCENE_DIRECTIONS[slug]
            seed = 271828 + index * 1009
            graph["6"]["inputs"]["prompt"] = prompt
            graph["6"]["inputs"]["negative_prompt"] = NEGATIVE
            graph["9"]["inputs"]["seed"] = seed
            graph["11"]["inputs"]["filename_prefix"] = f"cyberWife/scenes/{digest}_{slug}"
            generated = _comfy_output(_submit(graph)[0])
            raw = output_dir / f"{slug}.raw.png"
            raw_temporary = raw.with_suffix(".tmp.png")
            shutil.copy2(generated, raw_temporary)
            raw_temporary.replace(raw)
            target = output_dir / f"{slug}.png"
            composition = _normalize_composition(raw, target)
            records[slug] = {
                "scene_id": slug,
                "identity_sha256": _sha256(identity),
                "background_sha256": _sha256(background),
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "negative_prompt_sha256": hashlib.sha256(NEGATIVE.encode("utf-8")).hexdigest(),
                "seed": seed,
                "raw_output": str(raw),
                "raw_output_sha256": _sha256(raw),
                "output": str(target),
                "output_sha256": _sha256(target),
                "composition": composition,
                **_validate_keyframe(target),
            }
        manifest = {
            "schema_version": 1,
            "generation_mode": "local_qwen21_direct_complete_scene",
            "workflow_sha256": _sha256(WORKFLOW),
            "matting": False,
            "visual_approval_required": True,
            "appearance_id": appearance_id,
            "appearance_label": appearance_label,
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
    parser.add_argument("--identity", required=True, type=Path)
    parser.add_argument("--background-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--appearance",
        choices=("approved-red", "blue-white-floral"),
        default="approved-red",
    )
    parser.add_argument("--appearance-id")
    args = parser.parse_args()
    backgrounds = {
        slug: args.background_dir / f"{slug}.webp" for slug in SCENE_DIRECTIONS
    }
    prompt_base = (
        ALTERNATE_APPEARANCE_PROMPT_BASE
        if args.appearance == "blue-white-floral"
        else PROMPT_BASE
    )
    label = "蓝白碎花上衣" if args.appearance == "blue-white-floral" else "已批准红色针织上衣"
    print(json.dumps(run(
        args.identity,
        backgrounds,
        args.output_dir,
        prompt_base=prompt_base,
        appearance_id=args.appearance_id,
        appearance_label=label,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
