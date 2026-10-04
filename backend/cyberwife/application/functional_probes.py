"""Functional runtime probes used by health and release evidence collection."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx


@dataclass(frozen=True)
class ProbeResult:
    component: str
    status: str
    latency_ms: int
    checked_at: datetime
    logical_id: str | None = None
    device: str | None = None
    dtype: str | None = None
    error: str | None = None
    evidence: dict | None = None


class FunctionalProbeRunner:
    """Runs real probes; callers may inject functions only in contract tests."""

    _MODULES = {
        "vad": "tests.m0.verify_vad",
        "asr": "tests.m0.verify_asr",
        "tts": "tests.b0.verify_tts_runtime",
        "embedding": "tests.m0.verify_embedding",
        "avatar": "tests.m0.verify_avatar",
    }

    def __init__(
        self,
        repo_root: Path,
        *,
        llama_url: str = "http://127.0.0.1:8090",
        speech_url: str | None = "http://127.0.0.1:8091",
        avatar_url: str = "http://127.0.0.1:8010",
        gateway_url: str = "http://127.0.0.1:7860",
        timeout_s: float = 300.0,
        injected: dict[str, Callable[[], ProbeResult]] | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._llama_url = llama_url.rstrip("/")
        self._speech_url = speech_url.rstrip("/") if speech_url else None
        self._avatar_url = avatar_url.rstrip("/")
        self._gateway_url = gateway_url.rstrip("/")
        self._timeout_s = timeout_s
        self._injected = injected or {}

    def run(self, component: str) -> ProbeResult:
        started = time.perf_counter()
        checked_at = datetime.now(timezone.utc)
        try:
            if component in self._injected:
                return self._injected[component]()
            if component == "llm":
                evidence = self._probe_llm()
            elif component == "tts":
                evidence = self._probe_gateway_tts()
            elif component == "avatar":
                evidence = self._probe_avatar_or_checkpoint()
            elif component in {"vad", "asr", "tts", "embedding"} and self._speech_url:
                evidence = self._probe_speech(component)
            elif component in self._MODULES:
                evidence = self._probe_module(self._MODULES[component])
            else:
                raise ValueError(f"unknown component: {component}")
            latency = int((time.perf_counter() - started) * 1000)
            return ProbeResult(
                component=component,
                # Module verifiers use ``verified`` for artifact-level proof;
                # once the live endpoint has executed them successfully the
                # runtime contract is ``ready``. Only an explicit operational
                # fallback remains ``degraded``.
                status="degraded" if evidence.get("status") == "degraded" else "ready",
                latency_ms=latency,
                checked_at=checked_at,
                logical_id=str(evidence.get("logical_id") or component),
                device=evidence.get("device"),
                dtype=evidence.get("dtype"),
                evidence=evidence,
            )
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            return ProbeResult(
                component=component,
                status="error",
                latency_ms=latency,
                checked_at=checked_at,
                error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )

    def liveness(self, component: str) -> bool:
        """Fast process liveness only; it may downgrade but never promote ready."""
        if component in self._injected:
            return True
        try:
            if component == "llm":
                url = f"{self._llama_url}/health"
            elif component == "tts":
                # V1 CosyVoice is hosted in this Gateway process. snapshot()
                # itself runs inside /health, so an HTTP self-probe would
                # recurse and deadlock. Reaching snapshot proves the host is
                # live; synthesis readiness is exclusively promoted by the
                # real non-silent-audio functional probe in run("tts").
                return True
            elif component == "avatar":
                url = f"{self._avatar_url}/health"
            elif component in {"vad", "asr", "embedding"} and self._speech_url:
                url = f"{self._speech_url}/health"
            else:
                return False
            with httpx.Client(timeout=0.75, trust_env=False) as client:
                response = client.get(url)
                return response.status_code == 200
        except Exception:
            return False

    def _probe_llm(self) -> dict:
        with httpx.Client(timeout=10.0, trust_env=False) as client:
            health = client.get(f"{self._llama_url}/health")
            health.raise_for_status()
            response = client.post(
                f"{self._llama_url}/completion",
                json={"prompt": "只回答：好", "n_predict": 4, "temperature": 0, "stream": False},
            )
            response.raise_for_status()
            payload = response.json()
        if not str(payload.get("content", "")).strip():
            raise RuntimeError("llama completion returned empty content")
        return {"logical_id": "qwen3-14b-instruct-q4_k_m", "device": "cuda", "dtype": "q4_k_m"}

    def _probe_speech(self, component: str) -> dict:
        with httpx.Client(timeout=self._timeout_s, trust_env=False) as client:
            response = client.post(f"{self._speech_url}/api/v1/probe/{component}")
            response.raise_for_status()
            payload = response.json()
        if payload.get("status") != "ready":
            raise RuntimeError(payload.get("error") or f"{component} probe not ready")
        return payload

    def _probe_gateway_tts(self) -> dict:
        with httpx.Client(timeout=self._timeout_s, trust_env=False) as client:
            response = client.post(f"{self._gateway_url}/api/v1/internal/probe/tts")
            response.raise_for_status()
            payload = response.json()
        if payload.get("status") not in {"ready", "degraded"} or int(payload.get("non_silent_bytes", 0)) <= 0:
            raise RuntimeError(payload.get("error") or "gateway TTS probe not ready")
        return payload

    def _probe_avatar_or_checkpoint(self) -> dict:
        try:
            with httpx.Client(timeout=5.0, trust_env=False) as client:
                response = client.get(f"{self._avatar_url}/health")
                response.raise_for_status()
                payload = response.json()
            if payload.get("status") != "ready":
                raise RuntimeError(payload.get("error") or "avatar service not ready")
            return payload
        except (httpx.HTTPError, RuntimeError):
            # Checkpoint verification is useful evidence but cannot make the
            # running Avatar component ready; preserve the distinction.
            checkpoint = self._probe_module(self._MODULES["avatar"])
            raise RuntimeError(f"avatar service unavailable; checkpoint only: {checkpoint.get('status', 'verified')}")

    def _probe_module(self, module: str) -> dict:
        env = dict(__import__("os").environ)
        python_path = str(self._repo_root / "backend")
        env["PYTHONPATH"] = python_path + ((":" + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
        completed = subprocess.run(
            [sys.executable, "-m", module],
            cwd=self._repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=self._timeout_s,
            check=False,
        )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout)[-1000:]
            raise RuntimeError(f"{module} failed rc={completed.returncode}: {tail}")
        logical_id = module.rsplit("_", 1)[-1]
        marker = completed.stdout.rfind("\n{")
        if marker >= 0:
            candidate = completed.stdout[marker + 1 :].strip()
        elif completed.stdout.lstrip().startswith("{"):
            candidate = completed.stdout.strip()
        else:
            raise RuntimeError(f"{module} emitted no verification record for {logical_id}")
        try:
            record = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{module} emitted no parseable verification record") from exc
        if record.get("status") != "verified":
            raise RuntimeError(
                f"{module} reached {record.get('status', 'unknown')}, not verified: "
                f"{record.get('reason', 'no reason')}"
            )
        return record
