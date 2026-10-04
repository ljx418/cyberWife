from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_installer_requires_explicit_network_consent_and_checks_avatar_workflows():
    script = (ROOT / "ops/windows/Install-CyberWife.ps1").read_text(encoding="utf-8")
    assert "DependencyMode=online requires explicit -AllowNetworkInstall" in script
    assert "--no-index" in script and "--find-links" in script
    assert "function New-WslVenv" in script
    assert "function Test-WslVenv" in script
    assert "-m venv --clear" in script
    assert "include-system-site-packages = false" in script
    assert "'--clear', '--seed', '--python'" in script
    assert "python3.12-venv, uv, or virtualenv" in script
    assert "comfy.avatar_pipeline" in script
    assert "comfy_avatar_frontalize_api.json" in script
    assert "comfy_avatar_idle_api.json" in script


def test_runtime_uses_controlled_speech_python():
    script = (ROOT / "ops/windows/RuntimeLauncher.ps1").read_text(encoding="utf-8")
    assert "[string]$SpeechPythonWsl" in script
    speech_block = script.split("'speech' {", 1)[1].split("'avatar' {", 1)[0]
    assert "$SpeechPythonWsl" in speech_block
    assert "'python3', '-m', 'workers.speech_worker.server'" not in speech_block
    assert "ReadyStates = @('ready')" in script
    assert "ConvertFrom-Json" in script


def test_runtime_requirement_files_are_release_inputs():
    freezer = (ROOT / "ops/release_freeze.py").read_text(encoding="utf-8")
    for relative in (
        "backend/requirements-runtime-core-cu128.txt",
        "workers/avatar/requirements-runtime-cu128.txt",
    ):
        assert (ROOT / relative).is_file()
        assert relative in freezer


def test_isolated_runtime_verifier_checks_project_sources_and_no_system_packages():
    source = (ROOT / "ops/acceptance/verify_isolated_runtimes.py").read_text(encoding="utf-8")
    assert "include-system-site-packages = false" in source
    assert "cyberwife.api.server" in source
    assert "cosyvoice.cli.cosyvoice" in source
    assert "from avatars.wav2lip_avatar import LipReal" in source
    assert '"core_pip_check"' in source
    assert '"avatar_pip_check"' in source


def test_acc1_human_gate_requires_explicit_focus_consent_and_keeps_no_audio():
    script = (ROOT / "ops/acceptance/Invoke-ACC1HumanGate.ps1").read_text(encoding="utf-8")
    assert "-AcceptFocusChange" in script
    assert "stores_raw_audio = $false" in script
    assert "physical_mic_three_turns" in script
    assert "physical_mic_barge_in" in script
