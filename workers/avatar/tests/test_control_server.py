import json
import socket
import urllib.error
import urllib.request

import pytest

from control_server import AvatarControlServer


def _get(url: str, origin: str | None = None):
    headers = {"Origin": origin} if origin else {}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=2)


def test_control_server_is_minimal_loopback_and_releases_port():
    server = AvatarControlServer("127.0.0.1", 0)
    port = server.port
    server.start()
    try:
        with _get(f"http://127.0.0.1:{port}/healthz", "http://127.0.0.1:4173") as response:
            payload = json.loads(response.read())
            assert response.status == 200
            assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:4173"
            assert payload == {"status": "ready", "protocol": "avatar-control-v1"}
            assert not ({"text", "audio", "path", "model", "avatar_id"} & payload.keys())

        with pytest.raises(urllib.error.HTTPError) as rejected:
            _get(f"http://127.0.0.1:{port}/healthz", "https://public.example.test")
        assert rejected.value.code == 403
    finally:
        server.stop()

    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))


def test_control_server_rejects_non_loopback_bind():
    with pytest.raises(ValueError, match="loopback"):
        AvatarControlServer("0.0.0.0", 0)
