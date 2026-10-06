<# Read-only final V1 evidence aggregator. #>
[CmdletBinding()]
param(
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$PythonWsl = '',
    [ValidateSet('clean-machine', 'single-machine-portability')]
    [string]$DeploymentPolicy = 'single-machine-portability',
    [string]$DeploymentReport = '',
    [string]$OutputPath = 'C:\workSpace\cyberWife\audit\v1\V1FINAL\completion.json'
)

$ErrorActionPreference = 'Stop'

function Convert-WindowsPathToWsl([string]$Path) {
    $portablePath = $Path.Replace('\', '/')
    $converted = ((& wsl.exe -- wslpath -a -u $portablePath) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $converted.StartsWith('/')) {
        throw "failed to translate path to WSL: $Path"
    }
    return $converted
}

if ([string]::IsNullOrWhiteSpace($PythonWsl)) {
    $wslHome = ((& wsl.exe -- sh -lc 'printf %s "$HOME"') | Out-String).Trim()
    $PythonWsl = "$wslHome/.cyberWife/venvs/cosyvoice/bin/python"
}
$outputParent = Split-Path -Parent $OutputPath
if ($outputParent -and -not (Test-Path -LiteralPath $outputParent)) {
    New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
}
if ([string]::IsNullOrWhiteSpace($DeploymentReport)) {
    $reportName = if ($DeploymentPolicy -eq 'clean-machine') { 'INST1-AC06.json' } else { 'INST1-AC07.json' }
    $DeploymentReport = Join-Path $env:LOCALAPPDATA "cyberWife\acceptance\$reportName"
}
$installWsl = Convert-WindowsPathToWsl $DeploymentReport
$outputWsl = Convert-WindowsPathToWsl $OutputPath

& wsl.exe --cd $WorkspaceWsl env 'PYTHONPATH=.:backend' $PythonWsl `
    ops/acceptance/audit_v1_completion.py `
    --workspace $WorkspaceWsl `
    --deployment-report $installWsl `
    --deployment-policy $DeploymentPolicy `
    --output $outputWsl
exit $LASTEXITCODE
