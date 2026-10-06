<# Reduced V1 portability gate for owners who have only one physical machine. #>
[CmdletBinding()]
param(
    [switch]$AcceptReducedAssurance,
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$WheelhouseWsl = '',
    [string]$ArtifactReportWsl = '',
    [string]$PythonWsl = '',
    [string]$ReportPath = "$env:LOCALAPPDATA\cyberWife\acceptance\INST1-AC07.json",
    [string]$LlamaCppPath = 'C:\tools\llama.cpp\llama-server.exe',
    [string]$LlamaModelPath = 'C:\ComfyUI-aki-v2\ComfyUI\models\LLM\Qwen3-14B-Q4_K_M.gguf',
    [string]$AvatarModelWsl = '/mnt/c/ComfyUI-aki-v2/ComfyUI/models/Audio/wav2lip/wav2lip.pth'
)

$ErrorActionPreference = 'Stop'
if (-not $AcceptReducedAssurance) {
    throw '-AcceptReducedAssurance is required; this gate does not prove another Windows/WSL/GPU stack'
}
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'wsl.exe is required' }
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$launcher = Join-Path $repoRoot 'ops\windows\RuntimeLauncher.ps1'
$pidDir = Join-Path $env:LOCALAPPDATA 'cyberWife\pid'
$logDir = Join-Path $env:LOCALAPPDATA 'cyberWife\logs'
$wslHome = ((& wsl.exe -- sh -lc 'printf %s "$HOME"') | Out-String).Trim()
if (-not $wslHome.StartsWith('/')) { throw 'cannot resolve WSL home' }
if ([string]::IsNullOrWhiteSpace($WheelhouseWsl)) { $WheelhouseWsl = "$wslHome/.cyberWife/wheelhouse/cu128-py312" }
if ([string]::IsNullOrWhiteSpace($ArtifactReportWsl)) { $ArtifactReportWsl = "$wslHome/.cyberWife/audit/local-artifacts.json" }
if ([string]::IsNullOrWhiteSpace($PythonWsl)) { $PythonWsl = "$wslHome/.cyberWife/venvs/cosyvoice/bin/python" }
$steps = [System.Collections.Generic.List[object]]::new()
$lifecycleAttempted = $false

function Test-Endpoint([string]$Uri, [string[]]$States) {
    try {
        $response = Invoke-WebRequest -Uri $Uri -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -ne 200) { return $false }
        $payload = $response.Content | ConvertFrom-Json
        return $States -contains ([string]$payload.status).ToLowerInvariant()
    } catch { return $false }
}

function Test-Health {
    return (
        (Test-Endpoint 'http://127.0.0.1:8090/health' @('ok')) -and
        (Test-Endpoint 'http://127.0.0.1:8091/health' @('ready')) -and
        (Test-Endpoint 'http://127.0.0.1:8010/health' @('ready')) -and
        (Test-Endpoint 'http://127.0.0.1:8011/healthz' @('ready')) -and
        (Test-Endpoint 'http://127.0.0.1:7860/api/v1/health' @('ready', 'degraded'))
    )
}

function Test-PortsClosed {
    foreach ($port in @(7860, 8010, 8011, 8090, 8091)) {
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $task = $client.ConnectAsync('127.0.0.1', $port)
            if ($task.Wait(350) -and $client.Connected) { return $false }
        } catch { } finally { $client.Dispose() }
    }
    return @(Get-ChildItem -LiteralPath $pidDir -Filter '*.json' -ErrorAction SilentlyContinue).Count -eq 0
}

function Add-Step([string]$Name, [bool]$Pass) {
    $steps.Add([pscustomobject][ordered]@{ name = $Name; pass = $Pass })
    if (-not $Pass) { throw "acceptance step failed: $Name" }
}

function Invoke-Launcher([string]$Name, [string]$Action, [string]$Component = 'all', [bool]$Force = $false) {
    $arguments = @(
        '-Action', $Action, '-Component', $Component,
        '-WorkspaceWin', $WorkspaceWin, '-WorkspaceWsl', $WorkspaceWsl,
        '-LlamaCppPath', $LlamaCppPath, '-ModelPath', $LlamaModelPath,
        '-AvatarModelWsl', $AvatarModelWsl, '-PidDir', $pidDir, '-LogDir', $logDir,
        '-OfflineStrict'
    )
    if ($Force) { $arguments += '-Force' }
    # Invoke the launcher in-process. A nested powershell.exe connected to this
    # script's stdout pipeline can stay open while long-lived WSL services hold
    # inherited handles, even after RuntimeLauncher itself has returned.
    & $launcher @arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "runtime launcher failed: $Name" }
    if ($Action -eq 'stop') {
        Start-Sleep -Milliseconds 600
        Add-Step $Name (Test-PortsClosed)
    } else {
        Add-Step $Name (Test-Health)
    }
}

& wsl.exe -- $PythonWsl "$WorkspaceWsl/ops/acceptance/wheelhouse_manifest.py" verify --root $WheelhouseWsl | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'offline wheelhouse verification failed' }
& wsl.exe -- $PythonWsl "$WorkspaceWsl/ops/acceptance/prepare_local_artifacts.py" verify `
    --repo-root $WorkspaceWsl --data-root "$wslHome/.cyberWife" --report $ArtifactReportWsl | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'portable local artifact verification failed' }

$temporary = Join-Path $env:TEMP ("cyberwife-portability-" + [guid]::NewGuid().ToString('N') + '.json')
$completed = $false
try {
    $lifecycleAttempted = $true
    Invoke-Launcher 'start-1' 'start'
    Invoke-Launcher 'start-2' 'start'
    Invoke-Launcher 'status' 'status'
    Invoke-Launcher 'recover-avatar' 'recover' 'avatar' $true
    Invoke-Launcher 'stop-1' 'stop'
    Invoke-Launcher 'stop-2' 'stop'
    $completed = $true
} finally {
    if ($lifecycleAttempted -and -not (Test-PortsClosed)) {
        try {
            & $launcher `
                -Action stop -Force -WorkspaceWin $WorkspaceWin -WorkspaceWsl $WorkspaceWsl `
                -LlamaCppPath $LlamaCppPath -ModelPath $LlamaModelPath `
                -AvatarModelWsl $AvatarModelWsl -PidDir $pidDir -LogDir $logDir | Out-Null
        } catch { }
    }
    [ordered]@{
        schema_version = 1
        steps = @($steps)
        ports_closed_after = (Test-PortsClosed)
        completed = $completed
    } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temporary -Encoding UTF8
}

$lifecycleWsl = ((& wsl.exe -- wslpath -a $temporary) | Out-String).Trim()
$reportParent = Split-Path -Parent $ReportPath
if ($reportParent -and -not (Test-Path -LiteralPath $reportParent)) {
    New-Item -ItemType Directory -Force -Path $reportParent | Out-Null
}
$reportWsl = ((& wsl.exe -- wslpath -a $ReportPath) | Out-String).Trim()
try {
    & wsl.exe --cd $WorkspaceWsl env 'PYTHONPATH=ops/acceptance' $PythonWsl `
        ops/acceptance/build_single_machine_portability_report.py `
        --workspace $WorkspaceWsl --wheelhouse $WheelhouseWsl `
        --data-root "$wslHome/.cyberWife" `
        --artifact-report $ArtifactReportWsl --lifecycle $lifecycleWsl --output $reportWsl
    if ($LASTEXITCODE -ne 0) { throw 'single-machine portability report validation failed' }
} finally {
    Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue
}
