<# Build a component-separated, integrity-checked offline Python wheelhouse. #>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$AllowNetworkDownload,
    [switch]$ReplaceExisting,
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$PythonWsl = '',
    [string]$WheelhouseWsl = ''
)

$ErrorActionPreference = 'Stop'
if (-not $AllowNetworkDownload) {
    throw 'wheelhouse build accesses package indexes; pass -AllowNetworkDownload explicitly'
}
$wslHome = ((& wsl.exe -- sh -lc 'printf %s "$HOME"') | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $wslHome.StartsWith('/')) { throw 'cannot resolve WSL home' }
if (-not $PythonWsl) { $PythonWsl = "$wslHome/.cyberWife/venvs/cosyvoice/bin/python" }
if (-not $WheelhouseWsl) { $WheelhouseWsl = "$wslHome/.cyberWife/wheelhouse/cu128-py312" }
$staging = "$WheelhouseWsl.staging-$PID"
$backup = "$WheelhouseWsl.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$coreRequirements = "$WorkspaceWsl/backend/requirements-runtime-core-cu128.txt"
$avatarRequirements = "$WorkspaceWsl/workers/avatar/requirements-runtime-cu128.txt"
$manifestTool = "$WorkspaceWsl/ops/acceptance/wheelhouse_manifest.py"

function Invoke-Wsl([string[]]$Arguments) {
    & wsl.exe -- @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed: $($Arguments -join ' ')" }
}

Invoke-Wsl @($PythonWsl, '-c', 'import sys; raise SystemExit(sys.version_info[:2] != (3,12))')
& wsl.exe -- test -e $staging
if ($LASTEXITCODE -eq 0) { throw "staging path already exists: $staging" }
& wsl.exe -- test -e $WheelhouseWsl
$targetExists = ($LASTEXITCODE -eq 0)
if ($targetExists -and -not $ReplaceExisting) {
    throw "wheelhouse already exists; verify it or pass -ReplaceExisting: $WheelhouseWsl"
}

$built = $false
if ($PSCmdlet.ShouldProcess($WheelhouseWsl, 'build offline Python wheelhouse')) {
    Invoke-Wsl @('mkdir', '-p', "$staging/core", "$staging/avatar")
    Invoke-Wsl @($PythonWsl, '-m', 'pip', 'wheel', '--wheel-dir', "$staging/core", '-r', $coreRequirements)
    Invoke-Wsl @($PythonWsl, '-m', 'pip', 'wheel', '--wheel-dir', "$staging/avatar", '-r', $avatarRequirements)
    Invoke-Wsl @($PythonWsl, $manifestTool, 'build', '--root', $staging)
    Invoke-Wsl @($PythonWsl, $manifestTool, 'verify', '--root', $staging)
    if ($targetExists) { Invoke-Wsl @('mv', $WheelhouseWsl, $backup) }
    Invoke-Wsl @('mv', $staging, $WheelhouseWsl)
    $built = $true
}

[pscustomobject][ordered]@{
    schema_version = 1
    result = if ($built) { 'PASS' } else { 'SKIPPED' }
    wheelhouse_wsl = $WheelhouseWsl
    previous_backup_wsl = if ($built -and $targetExists) { $backup } else { $null }
} | ConvertTo-Json -Depth 4
