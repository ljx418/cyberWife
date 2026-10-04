"""Independent, loopback-only liveness endpoint for the Avatar process."""

from __future__ import annotations

import ipaddress
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


ALLOWED_ORIGINS = {
    "http://127.0.0.1:4173",
    "http://localhost:4173",
    "http://127.0.0.1:7860",
    "http://localhost:7860",
}


def _is_loopback(value: str) -> bool:
    if value in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


class _ControlHandler(BaseHTTPRequestHandler):
    server_version = "cyberWife-avatar-control/1"
    sys_version = ""

    def _origin_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        return origin in ALLOWED_ORIGINS and _is_loopback(parsed.hostname or "")

    def _send(self, status: int, payload: dict[str, str] | None = None) -> None:
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if not self._origin_allowed():
            self._send(403, {"status": "forbidden"})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        if self.path != "/healthz":
            self._send(404, {"status": "not_found"})
            return
        if not self._origin_allowed():
            self._send(403, {"status": "forbidden"})
            return
        self._send(200, {"status": "ready", "protocol": "avatar-control-v1"})

    def log_message(self, _format: str, *_args: object) -> None:
        # Liveness requests intentionally carry no user data and need no access log.
        return


class _LoopbackThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class AvatarControlServer:
    """Owns a tiny HTTP server on a thread independent from Avatar inference."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8011) -> None:
        if not _is_loopback(host):
            raise ValueError("Avatar control server must bind loopback")
        self._server = _LoopbackThreadingHTTPServer((host, port), _ControlHandler)
        self._thread = threading.Thread(
            name="avatar-control",
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.1},
            daemon=True,
        )

    @property
    def port(self) -> int:
        return int(self._server.server_address[1])

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)
