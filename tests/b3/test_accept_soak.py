import pytest

from tests.b3.accept_soak import project_component, resolve_active_avatar_id


def test_project_component_matches_only_real_service_argv():
    assert project_component("python -m cyberwife.api.server --port 7860") == "gateway"
    assert project_component("python3 -m workers.speech_worker.server --port 8091") == "speech"
    assert project_component("/venv/bin/python app.py --bind 127.0.0.1 --listenport 8010") == "avatar"


def test_project_component_rejects_diagnostic_shell_marker_text():
    assert project_component("bash -lc rg cyberwife.api.server backend") is None
    assert project_component("python -c 'print(\"workers.speech_worker.server\")'") is None
    assert project_component("bash -c 'echo app.py --bind 127.0.0.1 --listenport 8010'") is None


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload):
        self.payload = payload
        self.url = None

    def get(self, url):
        self.url = url
        return _Response(self.payload)


def test_resolve_active_avatar_id_uses_product_api():
    client = _Client({"avatar_id": "cropv2_avatar-1"})
    assert resolve_active_avatar_id(client, "http://127.0.0.1:7860") == "cropv2_avatar-1"
    assert client.url.endswith("/api/v1/avatar/active")


@pytest.mark.parametrize("value", ["", "../avatar", "avatar id", "x" * 81])
def test_resolve_active_avatar_id_rejects_missing_or_unsafe_values(value):
    with pytest.raises(ValueError, match="missing or unsafe"):
        resolve_active_avatar_id(_Client({"avatar_id": value}), "http://127.0.0.1:7860")
