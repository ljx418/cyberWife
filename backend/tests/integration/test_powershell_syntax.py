"""M1-08 PowerShell 启动器语法体检（PowerShell 不可在 WSL 跑，用 pwsh AST parser 校验语法）。

实际运行由 M1-11 端到端 smoke + 人工 AC-14 验证幂等性。
"""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PS_SCRIPTS = [
    REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1",
    REPO_ROOT / "ops" / "windows" / "StartLlamaCpp.ps1",
    REPO_ROOT / "ops" / "windows" / "ResolveWindowsHost.ps1",
]


def test_o2_launcher_profiles_are_bounded_and_explicit():
    source = (REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1").read_text(encoding="utf-8-sig")
    assert "LlamaSlotProfile" in source
    assert "ValidateSet('auto', 'dual', 'single')" in source
    assert "if ($LlamaSlotProfile -eq 'dual') { $args += @('--parallel', '2', '--kv-unified') }" in source
    assert "LlamaDisableContBatching" in source
    assert "LlamaNoHost" in source
    assert "[switch]$LlamaNoHost = $true" in source
    assert "if ($LlamaNoHost) { $args += '--no-host' }" in source
    assert "[int]$LlamaBatchSize = 512" in source
    assert "[int]$LlamaUbatchSize = 256" in source
    assert "'--batch-size', \"$LlamaBatchSize\", '--ubatch-size', \"$LlamaUbatchSize\"" in source
    assert "LlamaUbatchSize must be less than or equal to LlamaBatchSize" in source
    assert "[switch]$ReclaimWslCache = $true" in source
    assert "sync; echo 3 > /proc/sys/vm/drop_caches" in source
    assert "$started.Count -gt 0 -and $ReclaimWslCache" in source
    assert "frontend release build missing" in source
    assert "-RedirectStandardInput $stdin" in source
    assert "$process.Dispose()" in source
    assert "ValidateSet('qwen', 'cosy', 'cosy-trt')" in source
    assert "CW_TTS_MODEL" in source
    assert "CW_COSYVOICE_LOAD_TRT" in source
    assert "CW_TTS_FALLBACK_ACTIVE" in source
    assert "primary TTS gateway failed; starting one-way Qwen fallback" in source
    assert "FirstPlayableMinChars" in source
    assert "ValidateRange(4, 18)" in source


@pytest.fixture(scope="module")
def pwsh():
    path = shutil.which("pwsh") or shutil.which("powershell")
    if not path:
        pytest.skip("pwsh/powershell not available in WSL")
    return path


@pytest.mark.parametrize("script_path", PS_SCRIPTS, ids=lambda p: p.name)
def test_powershell_script_parses(script_path, pwsh):
    """pwsh -NoProfile -Command \"[System.Management.Automation.Language.Parser]::ParseFile(...)\" 返回 0 表示语法正确。"""
    assert script_path.exists(), f"missing: {script_path}"
    ps_path_win = str(script_path).replace("/", "\\")
    cmd = [
        pwsh, "-NoProfile", "-Command",
        f"$null = [System.Management.Automation.Language.Parser]::ParseFile('{ps_path_win}', [ref]$null, [ref]$null); 'OK'"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert "OK" in r.stdout, f"{script_path.name} parse error: stdout={r.stdout!r} stderr={r.stderr!r}"


def test_runtime_launcher_help_text(pwsh):
    """RuntimeLauncher 应有可识别动作（stop/status 等等）。本测试仅检查文件含必要关键字。"""
    content = (REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1").read_text()
    for keyword in ("start", "stop", "status", "recover", "restart", "loopback", "Test-Health"):
        assert keyword in content, f"RuntimeLauncher.ps1 missing keyword: {keyword}"


def test_runtime_launcher_never_kills_foreign_port_owner():
    content = (REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1").read_text()
    assert "no process was terminated" in content
    assert "refusing to kill" in content
    assert "Test-TcpListener" in content
    assert "WSL/unknown" in content
    assert "kill orphan" not in content
    assert "Stop-Process -Id $_.OwningProcess" not in content


def test_runtime_launcher_cleans_failed_component_record():
    content = (REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1").read_text()
    failed_health = content.index('if (-not (Wait-Endpoint $Name))')
    cleanup = content.index('Remove-OwnedRecord $Name', failed_health)
    failure = content.index('failed functional startup health', failed_health)
    assert failed_health < cleanup < failure


def test_release_acceptance_forces_and_verifies_avatar_recovery():
    source = (REPO_ROOT / "ops" / "acceptance" / "Invoke-V1ReleaseAcceptance.ps1").read_text(
        encoding="utf-8-sig"
    )
    assert "Invoke-Launcher recover avatar -Force" in source
    assert "& $launcher -Action $Action -Component $Component -Force" in source
    assert "& powershell.exe @launcherArgs" not in source
    assert "forced avatar recovery did not replace the avatar PID" in source
    assert "avatar recovery changed a healthy non-avatar PID" in source
    assert "$result.non_avatar_pids_unchanged" in source
    assert "$consecutiveReady -ge 3" in source
    assert "$windowsAvailable -ge 3072" in source


def test_runtime_launcher_uses_component_specific_health_and_valid_gateway_cli():
    content = (REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1").read_text()
    assert "8090/health" in content
    assert "8091/health" in content
    assert "8010/health" in content
    assert "7860/api/v1/health" in content
    assert "--config ' + $ConfigWsl" in content
    assert "$gatewayPython + ' -m cyberwife.api.server" in content
    assert "--version" in content
    assert "<1MB" not in content


def test_restart_preserves_component_and_runtime_configuration():
    content = (REPO_ROOT / "ops" / "windows" / "RuntimeLauncher.ps1").read_text()
    restart = content[content.index("'restart' {"):]
    assert "if ($Component -eq 'all')" in restart
    assert "-Action recover -Component $Component -Force" in restart
    for parameter in ("-ConfigWsl $ConfigWsl", "-TtsProfile $TtsProfile", "-PidDir $PidDir", "-LogDir $LogDir"):
        assert parameter in restart


def test_start_llamacpp_args_compatible_b11118():
    """b11118 llama-server CLI 兼容参数：-m, --host, --port, -c, --n-gpu-layers。"""
    content = (REPO_ROOT / "ops" / "windows" / "StartLlamaCpp.ps1").read_text()
    for arg in ("-m", "--host", "--port", "-c", "--n-gpu-layers"):
        assert arg in content, f"StartLlamaCpp.ps1 missing llama-server arg: {arg}"


def test_resolve_windows_host_falls_back():
    """ResolveWindowsHost 必须有 wsl + CIM 双 fallback。"""
    content = (REPO_ROOT / "ops" / "windows" / "ResolveWindowsHost.ps1").read_text()
    assert "wsl hostname -I" in content or "wsl.exe hostname -I" in content
    assert "Win32_NetworkAdapterConfiguration" in content
    assert "config\\runtime.local.toml" in content or "runtime.local.toml" in content
