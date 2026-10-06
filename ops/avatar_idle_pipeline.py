#!/usr/bin/env python3
"""Run the proven local portrait → frontal → 10s idle pipeline safely."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable

from ops.make_seamless_idle import encode, mean_absolute_error, palindrome_frames, read_frames
from ops.offline_scene_compositor import compose_scenes
from ops.scrfd_detector import detect_faces


ROOT = Path(__file__).resolve().parents[1]
COMFY_ROOT = Path("/mnt/c/ComfyUI-aki-v2/ComfyUI")
COMFY_PYTHON = Path("/mnt/c/ComfyUI-aki-v2/python/python.exe")
FACE_DETECTOR = COMFY_ROOT / "models/insightface/models/buffalo_l/det_10g.onnx"
BACKGROUND_ROOT = ROOT / "prototype/public/backgrounds"
RUNTIME_LAUNCHER = ROOT / "ops/windows/RuntimeLauncher.ps1"
RUNTIME_HEALTH = {
    "avatar": ("http://127.0.0.1:8010/health", "http://127.0.0.1:8011/healthz"),
    "speech": ("http://127.0.0.1:8091/health",),
    "llama": ("http://127.0.0.1:8090/health",),
    "gateway": ("http://127.0.0.1:7860/api/v1/health",),
}
REQUIRED_LOCAL_FILES = (
    COMFY_PYTHON,
    COMFY_ROOT / "main.py",
    ROOT / "ops/comfy_avatar_frontalize_api.json",
    ROOT / "ops/comfy_avatar_idle_api.json",
    FACE_DETECTOR,
    *(BACKGROUND_ROOT / name for name in (
        "blue-hour-living.webp", "garden-sunroom.webp",
        "morning-bedroom.webp", "rainy-library.webp",
    )),
    COMFY_ROOT / "models/diffusion_models/qwen-image-2.1-Q6_K.gguf",
    COMFY_ROOT / "models/text_encoders/qwen3vl_8b_bf16.safetensors",
    COMFY_ROOT / "models/vae/qwen_image_2.1_vae_bf16.safetensors",
    COMFY_ROOT / "models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
    COMFY_ROOT / "models/vae/wan_2.1_vae.safetensors",
    COMFY_ROOT / "models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    COMFY_ROOT / "models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
    COMFY_ROOT / "models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors",
    COMFY_ROOT / "models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors",
)


def _workflow_revision() -> str:
    """Bind reusable candidates to the exact image and motion workflows."""
    digest = hashlib.sha256()
    digest.update(b"full-frame-prompted-idle-v2\0")
    for name in ("comfy_avatar_frontalize_api.json", "comfy_avatar_idle_api.json"):
        digest.update((ROOT / "ops" / name).read_bytes())
    return digest.hexdigest()


def _windows_path(path: Path) -> str:
    value = str(path.resolve())
    if value.startswith("/mnt/") and len(value) > 7:
        return f"{value[5].upper()}:\\{value[7:].replace('/', chr(92))}"
    return value


def _request_json(url: str, payload: dict | None = None, timeout: float = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _local_ready(url: str) -> bool:
    try:
        _request_json(url, timeout=2)
        return True
    except Exception:
        return False


def _component_ready(component: str) -> bool:
    return all(_local_ready(url) for url in RUNTIME_HEALTH[component])


def _launcher(action: str, component: str) -> None:
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", _windows_path(RUNTIME_LAUNCHER),
        "-Action", action, "-Component", component,
    ]
    if action != "start":
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=180
        )
        if completed.returncode != 0:
            raise RuntimeError(f"runtime_{action}_{component}_failed")
        return

    # RuntimeLauncher persists ownership before waiting for the functional
    # endpoint. WSL interop can nevertheless keep its PowerShell wrapper alive
    # after the owned child is healthy, so health—not wrapper exit—is the gate.
    wrapper = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 360
    try:
        while time.monotonic() < deadline:
            if _component_ready(component):
                try:
                    wrapper.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    wrapper.terminate()
                    wrapper.wait(timeout=10)
                return
            code = wrapper.poll()
            if code is not None:
                if code != 0:
                    raise RuntimeError(f"runtime_{action}_{component}_failed")
                # A clean wrapper exit still requires the functional endpoint.
            time.sleep(1)
        raise RuntimeError(f"runtime_{action}_{component}_timeout")
    finally:
        if wrapper.poll() is None:
            wrapper.terminate()
            try:
                wrapper.wait(timeout=10)
            except subprocess.TimeoutExpired:
                wrapper.kill()
                wrapper.wait(timeout=10)


def _wait_comfy(process: subprocess.Popen, timeout: float = 150) -> None:
    deadline = time.monotonic() + timeout
    required = {"UnetLoaderGGUF", "TextEncodeQwenImage21", "WanImageToVideo"}
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("comfyui_start_failed")
        try:
            info = _request_json("http://127.0.0.1:8188/object_info", timeout=3)
            if required.issubset(info):
                return
        except Exception:
            pass
        time.sleep(1)
    raise RuntimeError("comfyui_start_timeout")


def _submit(graph: dict, timeout: float = 1200) -> list[dict]:
    queued = _request_json("http://127.0.0.1:8188/prompt", {"prompt": graph})
    prompt_id = queued["prompt_id"]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = _request_json(f"http://127.0.0.1:8188/history/{prompt_id}").get(prompt_id)
        if history:
            status = history.get("status", {})
            messages = status.get("messages", [])
            if any(item and item[0] == "execution_error" for item in messages):
                raise RuntimeError("comfyui_execution_failed")
            if status.get("completed"):
                outputs: list[dict] = []
                for node in history.get("outputs", {}).values():
                    for kind in ("images", "videos", "gifs"):
                        outputs.extend(node.get(kind, []))
                if not outputs:
                    raise RuntimeError("comfyui_output_missing")
                return outputs
        time.sleep(2)
    raise RuntimeError("comfyui_execution_timeout")


def _comfy_output(item: dict) -> Path:
    subfolder = str(item.get("subfolder", "")).replace("\\", "/")
    target = (COMFY_ROOT / "output" / subfolder / str(item["filename"])).resolve()
    output_root = (COMFY_ROOT / "output").resolve()
    if output_root not in target.parents or not target.is_file():
        raise RuntimeError("comfyui_output_invalid")
    return target


def _stop_comfy(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            timeout=20,
        )


def run_pipeline(
    source: Path,
    job_dir: Path,
    progress: Callable[[str, int], None] | None = None,
) -> dict:
    """Execute locally; output paths are confined to ``job_dir``."""
    progress = progress or (lambda _phase, _value: None)
    source = Path(source).resolve()
    job_dir = Path(job_dir).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    job_dir.mkdir(parents=True, exist_ok=True)
    missing = [path.name for path in REQUIRED_LOCAL_FILES if not path.is_file()]
    if missing:
        raise RuntimeError("avatar.local_model_missing:" + ",".join(missing))
    if shutil.disk_usage(job_dir).free < 5 * 1024**3:
        raise RuntimeError("avatar.insufficient_working_disk")
    if _local_ready("http://127.0.0.1:8188/object_info"):
        raise RuntimeError("avatar.comfyui_port_busy")
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    digest = source_sha256[:16]
    checkpoint_path = job_dir / "pipeline-result.json"
    checkpoint_frontal = job_dir / "frontal.png"
    checkpoint_video = job_dir / "idle-loop-10s.mp4"
    checkpoint_scenes = job_dir / "scenes" / "scene-composite-manifest.json"
    workflow_revision = _workflow_revision()
    if (
        checkpoint_path.is_file() and checkpoint_frontal.is_file()
        and checkpoint_video.is_file() and checkpoint_scenes.is_file()
    ):
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("source_sha256") == source_sha256
            and checkpoint.get("workflow_revision") == workflow_revision
            and checkpoint.get("output_frames") == 160
            and float(checkpoint.get("first_last_mae", 999)) <= 3.0
        ):
            progress("reusing_validated_checkpoint", 100)
            return {
                "frontal_path": str(checkpoint_frontal),
                "video_path": str(checkpoint_video),
                "scene_manifest_path": str(checkpoint_scenes),
                "metrics": checkpoint,
            }
    suffix = ".jpg" if source.suffix.lower() in {".jpg", ".jpeg"} else ".png"
    source_input = COMFY_ROOT / "input" / f"cw_idle_{digest}_source{suffix}"
    frontal_input = COMFY_ROOT / "input" / f"cw_idle_{digest}_frontal.png"
    process: subprocess.Popen | None = None
    stopped: list[str] = []
    log_stream = None
    try:
        progress("releasing_realtime_models", 5)
        for component in ("avatar", "speech", "llama"):
            if not _component_ready(component):
                continue
            _launcher("stop", component)
            stopped.append(component)
        shutil.copy2(source, source_input)
        # ComfyUI is a native Windows process and cannot consume a WSL ext4
        # path such as ~/.cyberWife. Keep only its non-sensitive runtime DB and
        # offline manager config on C:, while portraits/videos stay in job_dir.
        comfy_user = COMFY_ROOT / "user" / "cyberwife-runtime" / digest
        manager_dir = comfy_user / "__manager"
        manager_dir.mkdir(parents=True, exist_ok=True)
        (manager_dir / "config.ini").write_text(
            "[default]\nnetwork_mode = offline\ndb_mode = cache\n",
            encoding="utf-8",
        )
        log_stream = (job_dir / "comfyui.log").open("ab")
        process = subprocess.Popen(
            [
                str(COMFY_PYTHON), "-s", _windows_path(COMFY_ROOT / "main.py"),
                "--windows-standalone-build", "--listen", "127.0.0.1",
                "--port", "8188", "--disable-auto-launch",
                "--user-directory", _windows_path(comfy_user),
            ],
            cwd=COMFY_ROOT,
            stdout=log_stream,
            stderr=subprocess.STDOUT,
        )
        progress("starting_local_image_models", 12)
        _wait_comfy(process)

        progress("generating_frontal_portrait", 25)
        frontal_graph = json.loads(
            (ROOT / "ops/comfy_avatar_frontalize_api.json").read_text(encoding="utf-8")
        )
        frontal_graph["1"]["inputs"]["image"] = source_input.name
        frontal_graph["10"]["inputs"]["filename_prefix"] = f"cyberWife/jobs/{digest}_frontal"
        frontal_output = _comfy_output(_submit(frontal_graph)[0])
        frontal_path = job_dir / "frontal.png"
        shutil.copy2(frontal_output, frontal_path)
        shutil.copy2(frontal_output, frontal_input)

        progress("generating_idle_motion", 55)
        idle_graph = json.loads(
            (ROOT / "ops/comfy_avatar_idle_api.json").read_text(encoding="utf-8")
        )
        idle_graph["1"]["inputs"]["image"] = frontal_input.name
        idle_graph["17"]["inputs"]["filename_prefix"] = f"video/cyberWife/jobs/{digest}_idle"
        idle_output = _comfy_output(_submit(idle_graph)[0])
        source_idle = job_dir / "idle-source-5s.mp4"
        shutil.copy2(idle_output, source_idle)

        progress("closing_ten_second_loop", 88)
        frames, source_fps = read_frames(source_idle)
        # Preserve the model-generated full-frame motion.  Naturalness must be
        # created by the positive/negative prompt, never by transplanting an
        # eye strip or another local facial patch after generation.
        for index, frame in enumerate(frames[:80]):
            faces = detect_faces(frame, FACE_DETECTOR)
            if len(faces) != 1:
                raise RuntimeError(
                    f"avatar.idle_face_detection_failed:{index}:{len(faces)}"
                )
        loop = palindrome_frames(frames)
        video_path = job_dir / "idle-loop-10s.mp4"
        encode(loop, video_path)
        decoded, output_fps = read_frames(video_path)
        metrics = {
            "source_sha256": source_sha256,
            "workflow_revision": workflow_revision,
            "source_frames": len(frames),
            "source_fps": round(source_fps, 3),
            "output_frames": len(decoded),
            "output_fps": round(output_fps, 3),
            "duration_seconds": round(len(decoded) / output_fps, 3),
            "first_last_mae": round(mean_absolute_error(decoded[0], decoded[-1]), 4),
            "turnaround_mae": round(mean_absolute_error(decoded[79], decoded[80]), 4),
            "construction": "full_frame_prompted_motion_palindrome",
            "localized_facial_compositing": False,
        }
        if len(decoded) != 160 or metrics["first_last_mae"] > 3.0:
            raise RuntimeError("avatar.loop_validation_failed")
        progress("matting_whole_person", 90)
        scene_manifest = compose_scenes(
            video_path,
            {
                path.stem: path
                for path in sorted(BACKGROUND_ROOT.glob("*.webp"))
            },
            job_dir / "scenes",
        )
        metrics["scene_composites"] = {
            "count": len(scene_manifest["outputs"]),
            "mask_area_cv_percent": scene_manifest["mask_area_cv_percent"],
            "mask_temporal_delta_p95_percent": scene_manifest[
                "mask_temporal_delta_p95_percent"
            ],
        }
        checkpoint_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        progress("restoring_realtime_models", 95)
        return {
            "frontal_path": str(frontal_path),
            "video_path": str(video_path),
            "scene_manifest_path": str(job_dir / "scenes" / "scene-composite-manifest.json"),
            "metrics": metrics,
        }
    finally:
        _stop_comfy(process)
        if log_stream is not None:
            log_stream.close()
        for temporary in (source_input, frontal_input):
            temporary.unlink(missing_ok=True)
        restore_errors = []
        for component in reversed(stopped):
            try:
                _launcher("start", component)
            except Exception as exc:
                restore_errors.append(f"{component}:{exc}")
        if restore_errors:
            raise RuntimeError("runtime_restore_failed:" + ",".join(restore_errors))
