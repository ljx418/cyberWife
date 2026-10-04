#!/usr/bin/env python3
"""Verify fresh Core and Avatar virtual environments without loading models.

Every runtime probe is executed by the Python binary inside the target virtual
environment, so a passing report cannot be inherited from the development
interpreter.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


CORE_MODULES = (
    "fastapi,uvicorn,torch,torchaudio,faster_whisper,sentence_transformers,"
    "silero_vad,transformers,onnxruntime,httpx,yaml,multipart,sqlite_vec"
)
AVATAR_MODULES = "torch,torchaudio,cv2,aiortc,flask,numpy,diffusers,transformers"


def run(command: list[str], *, env: dict[str, str] | None = None) -> dict[str, object]:
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    return {
        "pass": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip()[-2000:],
        "stderr": completed.stderr.strip()[-2000:],
    }


def python_probe(python: Path, code: str, pythonpath: str | None = None) -> dict[str, object]:
    env = os.environ.copy()
    if pythonpath:
        env["PYTHONPATH"] = pythonpath
    return run([str(python), "-c", code], env=env)


def venv_is_isolated(venv: Path) -> bool:
    cfg = (venv / "pyvenv.cfg").read_text(encoding="utf-8").lower()
    return "include-system-site-packages = false" in cfg


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-venv", type=Path, required=True)
    parser.add_argument("--avatar-venv", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--cosy-source", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    core_python = args.core_venv / "bin" / "python"
    avatar_python = args.avatar_venv / "bin" / "python"
    core_path = ":".join((str(args.workspace / "backend"), str(args.workspace), str(args.cosy_source)))
    avatar_path = ":".join((str(args.workspace / "workers" / "avatar"), str(args.workspace)))

    checks = {
        "core_isolated": {"pass": venv_is_isolated(args.core_venv)},
        "avatar_isolated": {"pass": venv_is_isolated(args.avatar_venv)},
        "core_python_312": python_probe(core_python, "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))"),
        "avatar_python_312": python_probe(avatar_python, "import sys; raise SystemExit(sys.version_info[:2] != (3, 12))"),
        "core_pip_check": run([str(core_python), "-m", "pip", "check"]),
        "avatar_pip_check": run([str(avatar_python), "-m", "pip", "check"]),
        "core_dependencies": python_probe(core_python, f"import {CORE_MODULES}"),
        "avatar_dependencies": python_probe(avatar_python, f"import {AVATAR_MODULES}"),
        "core_project_sources": python_probe(
            core_python,
            "import cyberwife.api.server,workers.speech_worker.server,cosyvoice.cli.cosyvoice",
            core_path,
        ),
        "avatar_project_sources": python_probe(
            avatar_python,
            "import control_server,registry; from avatars.wav2lip_avatar import LipReal",
            avatar_path,
        ),
    }
    result = {
        "schema_version": 1,
        "stage": "INST1.2",
        "evidence_scope": "fresh_isolated_python_runtimes_without_model_loading",
        "checks": checks,
        "passed": all(bool(item["pass"]) for item in checks.values()),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
