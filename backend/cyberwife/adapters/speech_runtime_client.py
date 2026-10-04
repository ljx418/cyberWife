"""Loopback client for the isolated SpeechRuntime process."""
from __future__ import annotations

import httpx


class SpeechRuntimeClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8091", timeout_s: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> dict:
        response = httpx.post(
            f"{self._base_url}/api/v1/utterances/transcribe",
            content=pcm,
            headers={
                "content-type": "application/octet-stream",
                "x-sample-rate": str(sample_rate),
                "x-audio-channels": "1",
            },
            timeout=self._timeout_s,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("segments", []), list):
            raise RuntimeError("SpeechRuntime returned invalid segments")
        return payload

    def health(self) -> dict:
        response = httpx.get(f"{self._base_url}/health", timeout=2.0, trust_env=False)
        response.raise_for_status()
        return response.json()
