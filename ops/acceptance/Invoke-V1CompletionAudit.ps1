<# Read-only final V1 evidence aggregator. #>
[CmdletBinding()]
param(
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$PythonWsl = '',
    [string]$InstallationReport = "$env:LOCALAPPDATA\cyberWife\acceptance\INST1-AC06.json",
    [string]$OutputPath = 'C:\workSpace\cyberWife\audit\v1\V1FINAL\completion.json'
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($PythonWsl)) {
    $wslHome = ((& wsl.exe -- sh -lc 'printf %s "$HOME"') | Out-String).Trim()
    $PythonWsl = "$wslHome/.cyberWife/venvs/cosyvoice/bin/python"
}
$outputParent = Split-Path -Parent $OutputPath
if ($outputParent -and -not (Test-Path -LiteralPath $outputParent)) {
    New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
}
$installWsl = ((& wsl.exe -- wslpath -a $InstallationReport) | Out-String).Trim()
$outputWsl = ((& wsl.exe -- wslpath -a $OutputPath) | Out-String).Trim()
if (-not $installWsl.StartsWith('/') -or -not $outputWsl.StartsWith('/')) { throw 'failed to translate report paths to WSL' }

& wsl.exe --cd $WorkspaceWsl env 'PYTHONPATH=.:backend' $PythonWsl `
    ops/acceptance/audit_v1_completion.py `
    --workspace $WorkspaceWsl `
    --install $installWsl `
    --output $outputWsl
exit $LASTEXITCODE
