"""Windows RuntimeLauncher adapter used by recovery APIs."""
from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path


class LauncherService:
    _MAP = {
        "llm": "llama", "asr": "speech", "tts": "gateway",
        "embedding": "speech", "avatar": "avatar", "all": "all",
    }

    def __init__(self, repo_root: Path, *, timeout_s: float = 300.0, runner=None) -> None:
        self._repo_root = Path(repo_root)
        self._timeout_s = timeout_s
        self._runner = runner or subprocess.run

    def recover(self, component: str = "all") -> dict:
        target = self._MAP.get(component)
        if target is None:
            raise ValueError("unknown_component")
        script_path = str(self._repo_root / "ops" / "windows" / "RuntimeLauncher.ps1")
        if script_path.startswith("/mnt/") and len(script_path) > 7:
            drive = script_path[5].upper()
            script = drive + ":\\" + script_path[7:].replace("/", "\\")
        else:
            script = script_path
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script,
                   "-Action", "recover", "-Component", target]
        if self._runner is not subprocess.run:
            completed = self._runner(command, cwd=self._repo_root, capture_output=True, text=True, timeout=self._timeout_s)
            if completed.returncode != 0:
                raise RuntimeError("launcher_recover_failed")
        else:
            process = subprocess.Popen(
                command, cwd=self._repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            endpoints = {
                "llama": "http://127.0.0.1:8090/health",
                "speech": "http://127.0.0.1:8091/health",
                "avatar": "http://127.0.0.1:8010/health",
                "gateway": "http://127.0.0.1:7860/api/v1/health",
            }
            targets = list(endpoints) if target == "all" else [target]
            deadline = time.monotonic() + self._timeout_s
            while time.monotonic() < deadline:
                healthy = True
                for name in targets:
                    try:
                        with urllib.request.urlopen(endpoints[name], timeout=1.0) as response:
                            healthy = healthy and response.status == 200
                    except Exception:
                        healthy = False
                if healthy:
                    break
                if process.poll() not in (None, 0):
                    raise RuntimeError("launcher_recover_failed")
                time.sleep(0.25)
            else:
                raise RuntimeError("launcher_recover_timeout")
        return {"requested_component": component, "managed_component": target, "recovered": True}

    def schedule_recover(self, component: str, *, delay_s: int = 1) -> dict:
        """Schedule self-hosted Gateway/TTS recovery after the HTTP response flushes."""
        target = self._MAP.get(component)
        if target != "gateway":
            raise ValueError("scheduled_recovery_only_for_gateway")
        script_path = str(self._repo_root / "ops" / "windows" / "RuntimeLauncher.ps1")
        drive = script_path[5].upper() if script_path.startswith("/mnt/") else ""
        script = (drive + ":\\" + script_path[7:].replace("/", "\\")) if drive else script_path
        command = (
            f"Start-Sleep -Seconds {int(delay_s)}; & '{script}' -Action recover "
            "-Component gateway -Force"
        )
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=self._repo_root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"requested_component": component, "managed_component": target, "scheduled": True}
