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
    assert "wheelhouse_manifest.py" in script
    assert "wheelhouse-manifest.json" in script
    assert "--no-index" in script and "$componentWheelhouse" in script
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


def test_runtime_restores_the_persisted_active_avatar_by_default():
    script = (ROOT / "ops/windows/RuntimeLauncher.ps1").read_text(encoding="utf-8")
    assert "[string]$AvatarId = ''" in script
    assert "active_avatar_derivative" in script
    assert "d.status=''active''" in script
    assert "$resolvedAvatarId -match '^[A-Za-z0-9_-]{1,80}$'" in script
    assert "$AvatarId = 'wav2lip256_avatar1'" in script


def test_runtime_requirement_files_are_release_inputs():
    freezer = (ROOT / "ops/release_freeze.py").read_text(encoding="utf-8")
    for relative in (
        "backend/requirements-runtime-core-cu128.txt",
        "workers/avatar/requirements-runtime-cu128.txt",
    ):
        assert (ROOT / relative).is_file()
        assert relative in freezer
    assert "audit/v1/INST1/isolated-runtime-result.json" in freezer
    assert "audit/v1/INST1/offline-install-result.json" in freezer
    assert 'document.get("passed") is True' in freezer


def test_isolated_runtime_verifier_checks_project_sources_and_no_system_packages():
    source = (ROOT / "ops/acceptance/verify_isolated_runtimes.py").read_text(encoding="utf-8")
    assert "include-system-site-packages = false" in source
    assert "cyberwife.api.server" in source
    assert "cosyvoice.cli.cosyvoice" in source
    assert "from avatars.wav2lip_avatar import LipReal" in source
    assert '"core_pip_check"' in source
    assert '"avatar_pip_check"' in source


def test_wheelhouse_builder_requires_network_consent_and_integrity_manifest():
    builder = (ROOT / "ops/windows/Build-CyberWifeWheelhouse.ps1").read_text(encoding="utf-8")
    manifest = (ROOT / "ops/acceptance/wheelhouse_manifest.py").read_text(encoding="utf-8")
    assert "-AllowNetworkDownload explicitly" in builder
    assert '"$staging/core"' in builder and '"$staging/avatar"' in builder
    assert "pip', 'wheel'" in builder
    assert "wheelhouse_manifest.py" in builder
    assert "if ($built) { 'PASS' } else { 'SKIPPED' }" in builder
    assert "sha256" in manifest
    assert 'COMPONENTS = ("core", "avatar")' in manifest
    assert "os.link(core_wheel, avatar_wheel)" in manifest
    assert 'manifest.get("file_count") != len(expected)' in manifest


def test_offline_install_evidence_binds_no_index_and_runtime_checks():
    source = (ROOT / "ops/acceptance/verify_offline_install.py").read_text(encoding="utf-8")
    assert '"stage": "INST1.3"' in source
    assert "runtime_checks_10_of_10" in source
    assert "installer_no_index_contract" in source
    assert "manifest_sha256" in source


def test_acc1_human_gate_requires_explicit_focus_consent_and_keeps_no_audio():
    script = (ROOT / "ops/acceptance/Invoke-ACC1HumanGate.ps1").read_text(encoding="utf-8")
    assert "-AcceptFocusChange" in script
    assert "stores_raw_audio = $false" in script
    assert "acc1_human_gate.mjs" in script
    assert "--no-fake-media" in script


def test_acc1_machine_collector_proves_real_turns_without_storing_content():
    source = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "prototype/tests/acc1_human_gate.mjs",
            "prototype/tests/acc1_human_gate_core.mjs",
        )
    )
    assert "framereceived" in source and "framesent" in source
    assert "transcript.final" in source
    assert "reply.text.final" in source
    assert "reply.audio.chunk" in source
    assert "audio.playback.ended" in source
    assert "turn.cancelled" in source
    assert "barge_in.detected" in source
    assert "completedTurns.length >= 3" in source
    assert "postCancelCompleted" in source
    assert "stores_raw_audio: false" in source
    assert "text_final" not in source
    assert "text_delta" not in source
    assert "audio_chunk_b64" not in source
