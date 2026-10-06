import json
import subprocess
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
    assert (ROOT / "prototype/dist/index.html").is_file()
    assert "prototype/dist/" not in (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "prototype/dist/index.html"],
        capture_output=True,
    ).returncode == 0
    assert "offline prepare never runs npm ci" in script
    assert "$DependencyMode -ne 'online' -or -not $AllowNetworkInstall" in script


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
    wrapper = (ROOT / "ops/acceptance/Invoke-ACC1HumanGate.ps1").read_text(encoding="utf-8")
    assert "workspace-revision" in wrapper
    assert "status --porcelain --untracked-files=no" in wrapper
    assert "workspace_revision" in source


def test_inst1_clean_machine_gate_rejects_development_identity_and_requires_offline_lifecycle():
    source = (ROOT / "ops/acceptance/Invoke-INST1CleanMachineAcceptance.ps1").read_text(encoding="utf-8")
    assert "RejectWindowsSidHash" in source
    assert "RejectWslMachineIdHash" in source
    assert "AcceptCleanEnvironment" in source
    assert "'-DependencyMode', 'wheelhouse'" in source
    assert "-OfflineStrict" in source
    assert "Invoke-ManagedLifecycle 'start-1'" in source
    assert "Invoke-ManagedLifecycle 'start-2'" in source
    assert "Invoke-ManagedLifecycle 'status'" in source
    assert "Invoke-ManagedLifecycle 'recover-avatar'" in source
    assert source.count("Invoke-ManagedLifecycle 'stop-") >= 2
    assert "windows_sid_hash" in source and "wsl_machine_id_hash" in source
    assert "windows_sid =" not in source
    assert "wsl_machine_id =" not in source


def test_clean_install_is_driven_by_a_portable_private_artifact_manifest():
    installer = (ROOT / "ops/windows/Install-CyberWife.ps1").read_text(encoding="utf-8")
    gate = (ROOT / "ops/acceptance/Invoke-INST1CleanMachineAcceptance.ps1").read_text(encoding="utf-8")
    server = (ROOT / "backend/cyberwife/api/server.py").read_text(encoding="utf-8")
    launcher = (ROOT / "ops/windows/RuntimeLauncher.ps1").read_text(encoding="utf-8")
    assert "ArtifactManifestWsl" in installer and "prepare_local_artifacts.py" in installer
    assert "bootstrap/manifest.json" in installer
    assert "ArtifactManifestWsl" in gate and "artifact_manifest_sha256" in gate
    assert "assets/voice/user_clip_v2.wav" not in server
    assert "voice_reference_audio" in server and "bootstrap" in server
    assert "$DataRootWsl/bootstrap/avatar-id" in launcher
    example = json.loads((ROOT / "config/local-artifacts.example.json").read_text(encoding="utf-8"))
    assert example["format"] == "cyberwife-local-artifacts"
    assert all(example["models"][logical_id]["license_accepted"] is False for logical_id in example["models"])
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "config/local-artifacts.local.json" in ignored
    assert "config/local-artifacts.private.json" in ignored


def test_single_machine_portability_gate_is_explicit_offline_and_fail_closed():
    wrapper = (ROOT / "ops/acceptance/Invoke-INST1SingleMachinePortability.ps1").read_text(
        encoding="utf-8"
    )
    builder = (ROOT / "ops/acceptance/build_single_machine_portability_report.py").read_text(
        encoding="utf-8"
    )
    completion = (ROOT / "ops/acceptance/Invoke-V1CompletionAudit.ps1").read_text(
        encoding="utf-8"
    )
    assert "AcceptReducedAssurance" in wrapper
    assert "does not prove another Windows/WSL/GPU stack" in wrapper
    for step in ("start-1", "start-2", "status", "recover-avatar", "stop-1", "stop-2"):
        assert step in wrapper
    assert "wheelhouse_manifest.py" in wrapper
    assert "prepare_local_artifacts.py" in wrapper
    assert "ports_closed_after" in wrapper
    for limitation in ("same_windows_identity", "same_wsl_machine_id", "same_gpu_driver_stack"):
        assert limitation in builder
    assert "verify_wheelhouse" in builder
    assert "verify_published" in builder
    assert '"status", "--porcelain", "--untracked-files=no"' in builder
    assert "single-machine-portability" in completion
    assert "clean-machine" in completion
    assert "function Convert-WindowsPathToWsl" in completion
    assert "wslpath -a -u $portablePath" in completion


def test_single_machine_portability_gate_does_not_pipe_a_nested_powershell_launcher():
    wrapper = (ROOT / "ops/acceptance/Invoke-INST1SingleMachinePortability.ps1").read_text(
        encoding="utf-8-sig"
    )

    assert "& $launcher -Action $Action -Component $Component" in wrapper
    assert "& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher" not in wrapper
    assert "function Convert-WindowsPathToWsl" in wrapper
    assert ".Replace('\\', '/')" in wrapper
    assert "wslpath -a -u $portablePath" in wrapper
