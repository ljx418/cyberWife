<# Independent clean Windows-user + clean default-WSL acceptance orchestrator. #>
[CmdletBinding()]
param(
    [ValidateSet('fingerprint', 'accept')]
    [string]$Action = 'fingerprint',
    [switch]$AcceptCleanEnvironment,
    [string]$RejectWindowsSidHash = '',
    [string]$RejectWslMachineIdHash = '',
    [string]$WheelhouseWsl = '',
    [string]$ArtifactManifestWsl = '',
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$PythonWsl = 'python3',
    [string]$LlamaCppPath = 'C:\tools\llama.cpp\llama-server.exe',
    [string]$LlamaModelPath = 'C:\ComfyUI-aki-v2\ComfyUI\models\LLM\Qwen3-14B-Q4_K_M.gguf',
    [string]$AvatarModelWsl = '/mnt/c/ComfyUI-aki-v2/ComfyUI/models/Audio/wav2lip/wav2lip.pth',
    [string]$ComfyRootWsl = '/mnt/c/ComfyUI-aki-v2/ComfyUI',
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$installer = Join-Path $repoRoot 'ops\windows\Install-CyberWife.ps1'
$launcher = Join-Path $repoRoot 'ops\windows\RuntimeLauncher.ps1'
$pidDir = Join-Path $env:LOCALAPPDATA 'cyberWife\pid'
$logDir = Join-Path $env:LOCALAPPDATA 'cyberWife\logs'
$steps = [System.Collections.Generic.List[object]]::new()
$lifecycleAttempted = $false

function Get-Sha256Text([string]$Value) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value.Trim())
        return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

function Protect-ReportText([string]$Value) {
    return $Value `
        -replace '(?i)[A-Z]:\\Users\\[^\\\s]+', '%USERPROFILE%' `
        -replace '/home/[^/\s]+', '$HOME' `
        -replace '(?i)S-1-5-[0-9-]+', '<sid-redacted>'
}

function Invoke-WslText([string[]]$Arguments) {
    $value = ((& wsl.exe -- @Arguments 2>$null) | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "WSL read-only probe failed: $($Arguments[0])" }
    return $value
}

function Test-WslEntry([string]$Path, [string]$Kind = 'e') {
    & wsl.exe -- test "-$Kind" $Path
    return ($LASTEXITCODE -eq 0)
}

function Invoke-WslChecked([string[]]$Arguments) {
    & wsl.exe -- @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WSL operation failed: $($Arguments[0])" }
}

function Invoke-ChildPowerShell([string]$Script, [string[]]$Arguments) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Script @Arguments | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "child PowerShell failed: $([IO.Path]::GetFileName($Script))" }
}

function Add-Step([string]$Name, [bool]$Pass) {
    $steps.Add([pscustomobject][ordered]@{ name = $Name; pass = $Pass })
    if (-not $Pass) { throw "acceptance step failed: $Name" }
}

function Test-RuntimeHealth {
    $probes = @(
        @{ uri = 'http://127.0.0.1:8090/health'; states = @('ok') },
        @{ uri = 'http://127.0.0.1:8091/health'; states = @('ready') },
        @{ uri = 'http://127.0.0.1:8010/health'; states = @('ready') },
        @{ uri = 'http://127.0.0.1:8011/healthz'; states = @('ready') },
        @{ uri = 'http://127.0.0.1:7860/api/v1/health'; states = @('ready', 'degraded') }
    )
    foreach ($probe in $probes) {
        try {
            $response = Invoke-RestMethod -Uri $probe.uri -TimeoutSec 5
            if ($probe.states -notcontains [string]$response.status) { return $false }
        } catch { return $false }
    }
    return $true
}

function Test-ManagedPortsClosed {
    foreach ($port in @(7860, 8010, 8011, 8090, 8091)) {
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $task = $client.ConnectAsync('127.0.0.1', $port)
            if ($task.Wait(350) -and $client.Connected) { return $false }
        } catch { } finally { $client.Dispose() }
    }
    return @(Get-ChildItem -LiteralPath $pidDir -Filter '*.json' -ErrorAction SilentlyContinue).Count -eq 0
}

function Invoke-ManagedLifecycle([string]$Label, [string]$LifecycleAction, [string]$Component = 'all', [bool]$Force = $false) {
    $arguments = @(
        '-Action', $LifecycleAction,
        '-Component', $Component,
        '-WorkspaceWin', $WorkspaceWin,
        '-WorkspaceWsl', $WorkspaceWsl,
        '-LlamaCppPath', $LlamaCppPath,
        '-ModelPath', $LlamaModelPath,
        '-AvatarModelWsl', $AvatarModelWsl,
        '-PidDir', $pidDir,
        '-LogDir', $logDir,
        '-OfflineStrict'
    )
    if ($Force) { $arguments += '-Force' }
    Invoke-ChildPowerShell $launcher $arguments
    if ($LifecycleAction -eq 'stop') {
        Start-Sleep -Milliseconds 500
        Add-Step $Label (Test-ManagedPortsClosed)
    } else {
        Add-Step $Label (Test-RuntimeHealth)
    }
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'wsl.exe is required' }
if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) { throw 'installer missing' }
if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'runtime launcher missing' }

$windowsSidRaw = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$wslMachineIdRaw = Invoke-WslText @('cat', '/etc/machine-id')
$wslHome = Invoke-WslText @('sh', '-lc', 'printf %s "$HOME"')
if (-not $wslHome.StartsWith('/')) { throw 'cannot resolve WSL home' }
$windowsSidHash = Get-Sha256Text $windowsSidRaw
$wslMachineIdHash = Get-Sha256Text $wslMachineIdRaw
$dataRoot = "$wslHome/.cyberWife"
$runtimeConfig = Join-Path $WorkspaceWin 'config\runtime.local.toml'
$cleanBefore = [ordered]@{
    data_root_absent = -not (Test-WslEntry $dataRoot)
    core_venv_absent = -not (Test-WslEntry "$dataRoot/venvs/cosyvoice")
    avatar_venv_absent = -not (Test-WslEntry "$dataRoot/venvs/avatar-v1-py312")
    runtime_config_absent = -not (Test-Path -LiteralPath $runtimeConfig)
    model_registry_absent = -not (Test-Path -LiteralPath (Join-Path $WorkspaceWin 'config\model-registry.local.yaml'))
}
$fingerprint = [ordered]@{
    schema_version = 1
    action = $Action
    windows_sid_hash = $windowsSidHash
    wsl_machine_id_hash = $wslMachineIdHash
    windows_build = [Environment]::OSVersion.Version.ToString()
    wsl_kernel = Invoke-WslText @('uname', '-r')
    clean_before = $cleanBefore
}

if ($Action -eq 'fingerprint') {
    $fingerprint | ConvertTo-Json -Depth 5
    exit 0
}

if (-not $AcceptCleanEnvironment) { throw '-AcceptCleanEnvironment is required for accept' }
if ($RejectWindowsSidHash -notmatch '^[a-fA-F0-9]{64}$') { throw '-RejectWindowsSidHash must be the development fingerprint hash' }
if ($RejectWslMachineIdHash -notmatch '^[a-fA-F0-9]{64}$') { throw '-RejectWslMachineIdHash must be the development fingerprint hash' }
if ($windowsSidHash -eq $RejectWindowsSidHash.ToLowerInvariant()) { throw 'current Windows user matches the rejected development identity' }
if ($wslMachineIdHash -eq $RejectWslMachineIdHash.ToLowerInvariant()) { throw 'current WSL machine-id matches the rejected development identity or clone' }
if (@($cleanBefore.Values | Where-Object { -not $_ }).Count -ne 0) { throw 'environment is not clean before acceptance' }
if (-not (Test-WslEntry $WheelhouseWsl 'd')) { throw 'offline wheelhouse missing' }
if (-not (Test-WslEntry "$WheelhouseWsl/wheelhouse-manifest.json" 'f')) { throw 'wheelhouse integrity manifest missing' }
if (-not (Test-WslEntry $ArtifactManifestWsl 'f')) { throw 'local artifact manifest missing' }
$artifactDocument = (Invoke-WslText @('cat', $ArtifactManifestWsl)) | ConvertFrom-Json
if ($artifactDocument.schema_version -ne 1 -or $artifactDocument.format -ne 'cyberwife-local-artifacts') { throw 'local artifact manifest schema is invalid' }
$cosyVoiceSourceWsl = [string]$artifactDocument.cosyvoice_source.path
if (-not (Test-WslEntry $cosyVoiceSourceWsl 'd')) { throw 'local CosyVoice source artifact missing' }
$manifestLlamaModelWsl = [string]$artifactDocument.models.'qwen3-14b-instruct-q4_k_m'.path
$manifestAvatarModelWsl = [string]$artifactDocument.models.'livetalking-wav2lip256'.path
if (-not (Test-WslEntry $manifestLlamaModelWsl 'f') -or -not (Test-WslEntry $manifestAvatarModelWsl 'f')) { throw 'runtime model artifacts are missing' }
$LlamaModelPath = Invoke-WslText @('wslpath', '-w', $manifestLlamaModelWsl)
$AvatarModelWsl = $manifestAvatarModelWsl
$workspaceRevision = Invoke-WslText @('git', '-C', $WorkspaceWsl, 'rev-parse', 'HEAD')
if ($workspaceRevision -notmatch '^[a-fA-F0-9]{40,64}$') { throw 'workspace Git revision unavailable' }
$trackedChanges = Invoke-WslText @('git', '-C', $WorkspaceWsl, 'status', '--porcelain', '--untracked-files=no')
if ($trackedChanges) { throw 'workspace tracked files must be clean before acceptance' }
$wheelhouseManifestHash = ((Invoke-WslText @('sha256sum', "$WheelhouseWsl/wheelhouse-manifest.json")) -split '\s+')[0]
$artifactManifestHash = ((Invoke-WslText @('sha256sum', $ArtifactManifestWsl)) -split '\s+')[0]
$cosyVoiceRevision = Invoke-WslText @('git', '-C', $CosyVoiceSourceWsl, 'rev-parse', 'HEAD')
if ($wheelhouseManifestHash -notmatch '^[a-fA-F0-9]{64}$') { throw 'wheelhouse manifest hash unavailable' }
if ($artifactManifestHash -notmatch '^[a-fA-F0-9]{64}$') { throw 'local artifact manifest hash unavailable' }
if ($cosyVoiceRevision -notmatch '^[a-fA-F0-9]{40,64}$') { throw 'CosyVoice source revision unavailable' }

if ([string]::IsNullOrWhiteSpace($ReportPath)) {
    $ReportPath = Join-Path $env:LOCALAPPDATA 'cyberWife\acceptance\INST1-AC06.json'
}
$result = $null
$failure = $null
try {
    Invoke-ChildPowerShell $installer @(
        '-Action', 'prepare',
        '-DependencyMode', 'wheelhouse',
        '-WheelhouseWsl', $WheelhouseWsl,
        '-WorkspaceWin', $WorkspaceWin,
        '-WorkspaceWsl', $WorkspaceWsl,
        '-WslHome', $wslHome,
        '-PythonWsl', $PythonWsl,
        '-LlamaCppPath', $LlamaCppPath,
        '-LlamaModelPath', $LlamaModelPath,
        '-AvatarModelWsl', $AvatarModelWsl,
        '-ComfyRootWsl', $ComfyRootWsl,
        '-ArtifactManifestWsl', $ArtifactManifestWsl
    )
    Add-Step 'offline-prepare' $true
    Add-Step 'local-cosy-source' (Test-WslEntry "$dataRoot/src/CosyVoice" 'd')
    Invoke-ChildPowerShell $installer @(
        '-Action', 'verify',
        '-DependencyMode', 'none',
        '-WorkspaceWin', $WorkspaceWin,
        '-WorkspaceWsl', $WorkspaceWsl,
        '-WslHome', $wslHome,
        '-PythonWsl', $PythonWsl,
        '-LlamaCppPath', $LlamaCppPath,
        '-LlamaModelPath', $LlamaModelPath,
        '-AvatarModelWsl', $AvatarModelWsl,
        '-ComfyRootWsl', $ComfyRootWsl,
        '-ArtifactManifestWsl', $ArtifactManifestWsl
    )
    Add-Step 'installer-verify' $true
    $lifecycleAttempted = $true
    Invoke-ManagedLifecycle 'start-1' 'start'
    Invoke-ManagedLifecycle 'start-2' 'start'
    Invoke-ManagedLifecycle 'status' 'status'
    Invoke-ManagedLifecycle 'recover-avatar' 'recover' 'avatar' $true
    Invoke-ManagedLifecycle 'stop-1' 'stop'
    Invoke-ManagedLifecycle 'stop-2' 'stop'
    $result = [ordered]@{
        schema_version = 1
        gate = 'INST1-AC06-clean-machine'
        completed_at = (Get-Date -Format 'o')
        windows_sid_hash = $windowsSidHash
        wsl_machine_id_hash = $wslMachineIdHash
        identity_differs_from_development = $true
        workspace_revision = $workspaceRevision.ToLowerInvariant()
        wheelhouse_manifest_sha256 = $wheelhouseManifestHash.ToLowerInvariant()
        artifact_manifest_sha256 = $artifactManifestHash.ToLowerInvariant()
        cosyvoice_revision = $cosyVoiceRevision.ToLowerInvariant()
        windows_build = [Environment]::OSVersion.Version.ToString()
        wsl_kernel = Invoke-WslText @('uname', '-r')
        clean_before = $cleanBefore
        offline_only = $true
        steps = @($steps)
        result = 'PASS'
    }
} catch {
    $failure = Protect-ReportText $_.Exception.Message
    $result = [ordered]@{
        schema_version = 1
        gate = 'INST1-AC06-clean-machine'
        completed_at = (Get-Date -Format 'o')
        windows_sid_hash = $windowsSidHash
        wsl_machine_id_hash = $wslMachineIdHash
        identity_differs_from_development = ($windowsSidHash -ne $RejectWindowsSidHash.ToLowerInvariant() -and $wslMachineIdHash -ne $RejectWslMachineIdHash.ToLowerInvariant())
        workspace_revision = $workspaceRevision.ToLowerInvariant()
        wheelhouse_manifest_sha256 = $wheelhouseManifestHash.ToLowerInvariant()
        artifact_manifest_sha256 = $artifactManifestHash.ToLowerInvariant()
        cosyvoice_revision = $cosyVoiceRevision.ToLowerInvariant()
        windows_build = [Environment]::OSVersion.Version.ToString()
        wsl_kernel = Invoke-WslText @('uname', '-r')
        clean_before = $cleanBefore
        offline_only = $true
        steps = @($steps)
        result = 'FAIL'
        error = $failure
    }
} finally {
    if ($lifecycleAttempted) {
        try { Invoke-ManagedLifecycle 'cleanup-stop-1' 'stop' } catch { }
        try { Invoke-ManagedLifecycle 'cleanup-stop-2' 'stop' } catch { }
    }
}

$parent = Split-Path -Parent $ReportPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$result | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
$result | ConvertTo-Json -Depth 7
if ($result.result -ne 'PASS') { exit 2 }
