"""Loopback-only anti-corruption adapter for LiveTalking."""
from __future__ import annotations

import json
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cyberwife.ports.avatar import AvatarPort


class LiveTalkingAdapter(AvatarPort):
    def __init__(self, base_url: str = "http://127.0.0.1:8010", *, timeout_s: float = 2.0) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("LiveTalking endpoint must be loopback HTTP")
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s
        self._session_id: str | None = None
        self._generation = 0

    def begin_generation(self, generation: int) -> None:
        self._generation = int(generation)

    def _json(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(
            self._base_url + path,
            data=body,
            method=method,
            headers={"content-type": "application/json"},
        )
        with urlopen(request, timeout=self._timeout_s) as response:
            return json.loads(response.read())

    def open(self, session_id: str = "0") -> str:
        result = self._json("POST", "/api/v1/media/open", {"session_id": session_id})
        self._session_id = str(result["data"]["session_id"])
        return self._session_id

    def start_session(self, avatar_image_path: str) -> str:
        del avatar_image_path  # V1 uses the configured, consented portrait entity.
        return self.open("0")

    def push_audio(self, pcm_frame: bytes, *, clock_ms: int) -> None:
        if self._session_id is None:
            raise RuntimeError("avatar session is not open")
        if len(pcm_frame) != 640:
            raise ValueError("avatar PCM frame must be 640 bytes")
        request = Request(
            f"{self._base_url}/api/v1/media/{self._session_id}/audio?clock_ms={clock_ms}&generation={self._generation}",
            data=pcm_frame,
            method="POST",
            headers={"content-type": "application/octet-stream"},
        )
        # Audio is already played independently by the browser.  Fail the
        # optional lip-sync feed quickly so Avatar loss reaches the UI within
        # the two-second degradation budget instead of stalling every frame.
        with urlopen(request, timeout=min(self._timeout_s, 0.35)) as response:
            json.loads(response.read())

    def push_audio_chunk(self, session_id: str, pcm_frame: bytes) -> None:
        if self._session_id != session_id:
            self._session_id = session_id
        self.push_audio(pcm_frame, clock_ms=0)

    def cancel(self) -> None:
        if self._session_id is not None:
            self._json("POST", f"/api/v1/media/{self._session_id}/cancel", {})

    def health(self) -> dict:
        return self._json("GET", "/health")

    def metrics(self) -> dict:
        if self._session_id is None:
            return {"status": "closed"}
        return self._json("GET", f"/api/v1/media/{self._session_id}/metrics")["data"]

    def close(self) -> None:
        if self._session_id is not None:
            self._json("POST", f"/api/v1/media/{self._session_id}/close", {})
            self._session_id = None

    def end_session(self, session_id: str) -> None:
        if self._session_id == session_id:
            self.close()
