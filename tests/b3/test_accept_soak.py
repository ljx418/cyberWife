from tests.b3.accept_soak import project_component


def test_project_component_matches_only_real_service_argv():
    assert project_component("python -m cyberwife.api.server --port 7860") == "gateway"
    assert project_component("python3 -m workers.speech_worker.server --port 8091") == "speech"
    assert project_component("/venv/bin/python app.py --bind 127.0.0.1 --listenport 8010") == "avatar"


def test_project_component_rejects_diagnostic_shell_marker_text():
    assert project_component("bash -lc rg cyberwife.api.server backend") is None
    assert project_component("python -c 'print(\"workers.speech_worker.server\")'") is None
    assert project_component("bash -c 'echo app.py --bind 127.0.0.1 --listenport 8010'") is None
