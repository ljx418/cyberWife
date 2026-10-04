<#
.SYNOPSIS
  cyberWife V1 Windows + WSL2 lifecycle supervisor.
.DESCRIPTION
  Starts, probes, recovers and stops only processes recorded and owned by this
  launcher. A foreign port owner is a hard failure and is never terminated.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('start', 'stop', 'status', 'recover', 'restart')]
    [string]$Action,
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$LlamaCppPath = 'C:\tools\llama.cpp\llama-server.exe',
    [string]$ModelPath = 'C:\ComfyUI-aki-v2\ComfyUI\models\LLM\Qwen3-14B-Q4_K_M.gguf',
    [string]$AvatarModelWsl = '/mnt/c/ComfyUI-aki-v2/ComfyUI/models/Audio/wav2lip/wav2lip.pth',
    [string]$AvatarId = 'wav2lip256_avatar1',
    [string]$AvatarPythonWsl = '/home/administrator/.cyberWife/venvs/avatar-v1-py312/bin/python',
    [string]$ConfigWsl = 'config/runtime.local.toml',
    [ValidateSet('auto', 'dual', 'single')]
    [string]$LlamaSlotProfile = 'auto',
    # Single-user V1 does not need llama.cpp's 2048-token prefill workspace.
    # Keep the 4096-token context intact while bounding transient host/GPU RAM.
    [ValidateRange(128, 2048)]
    [int]$LlamaBatchSize = 512,
    [ValidateRange(64, 512)]
    [int]$LlamaUbatchSize = 256,
    [switch]$LlamaDisableContBatching,
    # Validated on the target RTX 4090 host: lowers Windows pressure without
    # changing the model, slot count or 4096-token prompt contract. Roll back
    # explicitly with -LlamaNoHost:$false.
    [switch]$LlamaNoHost = $true,
    # Reclaims only clean WSL file cache after a newly started full stack. This
    # is reversible (cache is repopulated on demand) and can be disabled.
    [switch]$ReclaimWslCache = $true,
    [ValidateSet('qwen', 'cosy', 'cosy-trt')]
    [string]$TtsProfile = 'cosy',
    [switch]$TtsFallbackActive,
    [ValidateSet('all', 'llama', 'speech', 'avatar', 'gateway')]
    [string]$Component = 'all',
    [string]$CosyVoicePythonWsl = '/home/administrator/.cyberWife/venvs/cosyvoice/bin/python',
    [ValidateRange(4, 18)]
    [int]$FirstPlayableMinChars = 10,
    [string]$PidDir = "$env:LOCALAPPDATA\cyberWife\pid",
    [string]$LogDir = "$env:LOCALAPPDATA\cyberWife\logs",
    [switch]$OfflineStrict,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
if ($LlamaUbatchSize -gt $LlamaBatchSize) {
    throw 'LlamaUbatchSize must be less than or equal to LlamaBatchSize'
}
$Components = [ordered]@{
    llama = @{ Port = 8090; Marker = 'llama-server'; Health = 'http://127.0.0.1:8090/health' }
    speech = @{ Port = 8091; Marker = 'workers.speech_worker.server'; Health = 'http://127.0.0.1:8091/health' }
    avatar = @{ Port = 8010; Marker = 'app.py --bind 127.0.0.1'; Health = 'http://127.0.0.1:8010/health'; ControlHealth = 'http://127.0.0.1:8011/healthz' }
    gateway = @{ Port = 7860; Marker = 'cyberwife.api.server'; Health = 'http://127.0.0.1:7860/api/v1/health' }
}

function Write-Stage([string]$Message) {
    $ts = Get-Date -Format 'yyyy-MM-ddTHH:mm:ss.fffzzz'
    Write-Host "[$ts] $Message"
}

function Get-PidPath([string]$Name) { return Join-Path $PidDir "$Name.json" }

function Save-OwnedProcess([string]$Name, [System.Diagnostics.Process]$Process, [string]$Marker) {
    if (-not (Test-Path $PidDir)) { New-Item -ItemType Directory -Force -Path $PidDir | Out-Null }
    [ordered]@{ name = $Name; pid = $Process.Id; marker = $Marker; started_at = (Get-Date -Format 'o') } |
        ConvertTo-Json | Set-Content -Encoding UTF8 -Path (Get-PidPath $Name)
}

function Get-OwnedRecord([string]$Name) {
    $path = Get-PidPath $Name
    if (-not (Test-Path $path)) { return $null }
    try { return Get-Content -Raw $path | ConvertFrom-Json } catch { return $null }
}

function Test-OwnedProcess([string]$Name) {
    $record = Get-OwnedRecord $Name
    if (-not $record) { return $false }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)" -ErrorAction SilentlyContinue
    if (-not $process) { return $false }
    return (($process.CommandLine -as [string]) -like "*$($record.marker)*")
}

function Remove-OwnedRecord([string]$Name) {
    $path = Get-PidPath $Name
    if (Test-Path $path) { Remove-Item -Force $path }
}

function Test-Endpoint([string]$Uri, [int]$TimeoutSec = 2) {
    try {
        $response = Invoke-WebRequest -Uri $Uri -TimeoutSec $TimeoutSec -UseBasicParsing -ErrorAction Stop
        return ($response.StatusCode -eq 200)
    } catch { return $false }
}

function Test-ComponentEndpoint([string]$Name) {
    if (-not (Test-Endpoint $Components[$Name].Health)) { return $false }
    if ($Name -eq 'avatar' -and -not (Test-Endpoint $Components[$Name].ControlHealth)) { return $false }
    return $true
}

function Test-TcpListener([int]$Port, [int]$TimeoutMs = 1000) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync('127.0.0.1', $Port)
        return ($task.Wait($TimeoutMs) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Assert-PortAvailable([string]$Name) {
    $port = $Components[$Name].Port
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    # A WSL listener is reachable through localhost forwarding/mirrored networking,
    # but is not guaranteed to appear in the Windows TCP table. Probe the socket too.
    if (-not $listener -and -not (Test-TcpListener $port)) { return }
    if ((Test-OwnedProcess $Name) -and (Test-ComponentEndpoint $Name)) { return }
    $owner = if ($listener) { $listener.OwningProcess } else { 'WSL/unknown' }
    throw "port $port is owned by a foreign or stale process (PID=$owner); no process was terminated"
}

function Wait-Endpoint([string]$Name, [int]$TimeoutSec = 120) {
    for ($i = 0; $i -lt $TimeoutSec; $i++) {
        if (Test-ComponentEndpoint $Name) { return $true }
        if ((Get-OwnedRecord $Name) -and -not (Test-OwnedProcess $Name)) { return $false }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Start-ManagedComponent([string]$Name) {
    if ((Test-OwnedProcess $Name) -and (Test-ComponentEndpoint $Name)) {
        Write-Stage "$Name already healthy; keeping owned instance"
        return $false
    }
    if (Get-OwnedRecord $Name) { Remove-OwnedRecord $Name }
    Assert-PortAvailable $Name
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }
    $stdout = Join-Path $LogDir "$Name.log"
    $stderr = Join-Path $LogDir "$Name.err.log"
    # A Windows child launched through WSL interop must not inherit the relay's
    # stdin handle.  Otherwise the WSL `/init` bridge waits for the long-lived
    # child even after this launcher has printed success, blocking the .cmd.
    $stdin = Join-Path $LogDir "$Name.stdin"
    if (-not (Test-Path $stdin)) { Set-Content -Path $stdin -Value '' -NoNewline }
    switch ($Name) {
        'llama' {
            # Prompt contract needs <=4096 input tokens plus bounded short output;
            # V1 prompt contract is capped at 4096 tokens.  A 4096 KV cache
            # avoids reserving memory the product contract cannot consume.
            $args = @('-m', $ModelPath, '--host', '127.0.0.1', '--port', '8090', '-c', '4096', '--n-gpu-layers', '40', '--batch-size', "$LlamaBatchSize", '--ubatch-size', "$LlamaUbatchSize")
            if ($LlamaSlotProfile -eq 'dual') { $args += @('--parallel', '2', '--kv-unified') }
            if ($LlamaSlotProfile -eq 'single') { $args += @('--parallel', '1') }
            if ($LlamaDisableContBatching) { $args += '--no-cont-batching' }
            if ($LlamaNoHost) { $args += '--no-host' }
            $process = Start-Process -FilePath $LlamaCppPath -ArgumentList $args -RedirectStandardInput $stdin -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
        }
        'speech' {
            $args = @('--cd', $WorkspaceWsl, 'env', 'PYTHONPATH=backend:.', 'HF_HUB_OFFLINE=1', 'TRANSFORMERS_OFFLINE=1', 'python3', '-m', 'workers.speech_worker.server', '--host', '127.0.0.1', '--port', '8091', '--probe-timeout', '120', '--asr-device', 'cuda', '--asr-compute-type', 'float16')
            $process = Start-Process -FilePath 'wsl.exe' -ArgumentList $args -RedirectStandardInput $stdin -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
        }
        'avatar' {
            $args = @('--cd', "$WorkspaceWsl/workers/avatar", 'env', 'HF_HUB_OFFLINE=1', 'TRANSFORMERS_OFFLINE=1', 'CW_AVATAR_DATA_ROOT=/home/administrator/.cyberWife/avatar/avatars', $AvatarPythonWsl, 'app.py', '--bind', '127.0.0.1', '--listenport', '8010', '--control-port', '8011', '--transport', 'ws_h264', '--tts', 'external', '--max_session', '1', '--model', 'wav2lip', '--batch_size', '8', '--modelfile', $AvatarModelWsl, '--avatar_id', $AvatarId)
            $process = Start-Process -FilePath 'wsl.exe' -ArgumentList $args -RedirectStandardInput $stdin -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
        }
        'gateway' {
            $ttsModel = if ($TtsProfile -eq 'qwen') { 'qwen3-tts-12hz-1.7b-base' } else { 'cosyvoice2-0.5b' }
            $ttsTrt = if ($TtsProfile -eq 'cosy-trt') { '1' } else { '0' }
            $gatewayPython = if ($TtsProfile -eq 'qwen') { 'python3' } else { $CosyVoicePythonWsl }
            $ttsFallback = if ($TtsFallbackActive) { '1' } else { '0' }
            $shell = 'CW_LIBS=$(find /home/administrator/.local/lib/python3.12/site-packages/nvidia -mindepth 2 -maxdepth 2 -type d -name lib -print | paste -sd: -); export LD_LIBRARY_PATH="$CW_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" PYTHONPATH=backend:. HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MODELSCOPE_OFFLINE=1 CW_TTS_MODEL=' + $ttsModel + ' CW_TTS_FALLBACK_ACTIVE=' + $ttsFallback + ' CW_COSYVOICE_LOAD_TRT=' + $ttsTrt + ' CW_FIRST_PLAYABLE_MIN_CHARS=' + $FirstPlayableMinChars + '; exec ' + $gatewayPython + ' -m cyberwife.api.server --config ' + $ConfigWsl + ' --host 127.0.0.1 --port 7860'
            $args = @('--cd', $WorkspaceWsl, 'bash', '-lc', $shell)
            $process = Start-Process -FilePath 'wsl.exe' -ArgumentList $args -RedirectStandardInput $stdin -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
        }
        default { throw "unknown component $Name" }
    }
    # Start-Process keeps a System.Diagnostics.Process handle.  With redirected
    # stdout/stderr that handle can keep the non-interactive PowerShell host
    # alive for the whole lifetime of the child, which blocks Start-cyberWife.cmd
    # before it can open the browser.  Persist the PID, then release only the
    # parent-side handle; this does not terminate or detach ownership of child.
    $processId = $process.Id
    Save-OwnedProcess $Name $process $Components[$Name].Marker
    $process.Dispose()
    if (-not (Wait-Endpoint $Name)) {
        if (Test-OwnedProcess $Name) {
            Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
        }
        Remove-OwnedRecord $Name
        throw "$Name failed functional startup health; see $stderr"
    }
    Write-Stage "$Name ready PID=$processId"
    return $true
}

function Stop-ManagedComponent([string]$Name) {
    $record = Get-OwnedRecord $Name
    if (-not $record) { return }
    if (-not (Test-OwnedProcess $Name)) {
        Write-Stage "$Name PID record is stale or ownership marker mismatched; refusing to kill PID=$($record.pid)"
        Remove-OwnedRecord $Name
        return
    }
    Stop-Process -Id ([int]$record.pid) -Force -ErrorAction SilentlyContinue
    Remove-OwnedRecord $Name
    Write-Stage "$Name stopped PID=$($record.pid)"
}

function Assert-Preflight {
    if (-not (Test-Path $WorkspaceWin)) { throw "workspace missing: $WorkspaceWin" }
    if (-not (Test-Path $LlamaCppPath)) { throw "llama-server missing: $LlamaCppPath" }
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $llamaVersion = & $LlamaCppPath --version 2>&1
    $llamaVersionExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($llamaVersionExit -ne 0 -or -not (($llamaVersion -join ' ') -match 'build [0-9]+')) {
        throw "llama-server runtime probe failed: $LlamaCppPath"
    }
    if (-not (Test-Path $ModelPath)) { throw "LLM model missing: $ModelPath" }
    $frontendIndex = Join-Path $WorkspaceWin 'prototype\dist\index.html'
    if (-not (Test-Path $frontendIndex)) {
        throw "frontend release build missing: $frontendIndex (run npm run build in prototype)"
    }
    & wsl.exe --cd $WorkspaceWsl test -f $ConfigWsl
    if ($LASTEXITCODE -ne 0) { throw "WSL runtime config missing: $ConfigWsl" }
    & wsl.exe test -x $AvatarPythonWsl
    if ($LASTEXITCODE -ne 0) { throw "Avatar Python runtime missing: $AvatarPythonWsl" }
    if ($TtsProfile -ne 'qwen') {
        & wsl.exe test -x $CosyVoicePythonWsl
        if ($LASTEXITCODE -ne 0) { throw "CosyVoice Python runtime missing: $CosyVoicePythonWsl" }
    }
}

function Get-StatusReport {
    $items = [ordered]@{}
    foreach ($name in $Components.Keys) {
        $record = Get-OwnedRecord $name
        $items[$name] = [ordered]@{
            pid = if ($record) { $record.pid } else { $null }
            owned = (Test-OwnedProcess $name)
            healthy = (Test-ComponentEndpoint $name)
            port = $Components[$name].Port
            health = $Components[$name].Health
        }
    }
    return [ordered]@{ ts = (Get-Date -Format 'o'); components = $items }
}

function Invoke-WslCacheReclaim {
    Write-Stage 'requesting one-time WSL clean page-cache reclaim'
    & wsl.exe -u root -- sh -c 'sync; echo 3 > /proc/sys/vm/drop_caches'
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'WSL page-cache reclaim failed; resource headroom gate must decide readiness'
        return $false
    }
    Write-Stage 'WSL clean page-cache reclaim requested'
    return $true
}

switch ($Action) {
    'start' {
        Assert-Preflight
        $started = New-Object System.Collections.Generic.List[string]
        try {
            foreach ($name in @('llama', 'speech', 'avatar', 'gateway')) {
                try {
                    if (Start-ManagedComponent $name) { $started.Add($name) }
                } catch {
                    if ($name -eq 'gateway' -and $TtsProfile -ne 'qwen') {
                        Write-Stage "primary TTS gateway failed; starting one-way Qwen fallback"
                        $TtsProfile = 'qwen'
                        $TtsFallbackActive = $true
                        if (Start-ManagedComponent $name) { $started.Add($name) }
                    } else {
                        throw
                    }
                }
            }
            if ($Component -eq 'all' -and $started.Count -gt 0 -and $ReclaimWslCache) {
                [void](Invoke-WslCacheReclaim)
            }
            Get-StatusReport | ConvertTo-Json -Depth 5
        } catch {
            Write-Stage "start failed; rolling back only processes created by this invocation"
            for ($i = $started.Count - 1; $i -ge 0; $i--) { Stop-ManagedComponent $started[$i] }
            throw
        }
    }
    'stop' {
        $targets = if ($Component -eq 'all') { @('gateway', 'avatar', 'speech', 'llama') } else { @($Component) }
        foreach ($name in $targets) { Stop-ManagedComponent $name }
        Get-StatusReport | ConvertTo-Json -Depth 5
    }
    'status' { Get-StatusReport | ConvertTo-Json -Depth 5 }
    'recover' {
        Assert-Preflight
        $targets = if ($Component -eq 'all') { @('llama', 'speech', 'avatar', 'gateway') } else { @($Component) }
        foreach ($name in $targets) {
            if ($Force -or -not (Test-ComponentEndpoint $name)) {
                Stop-ManagedComponent $name
                [void](Start-ManagedComponent $name)
            }
        }
        Get-StatusReport | ConvertTo-Json -Depth 5
    }
    'restart' {
        if ($Component -eq 'all') {
            & $PSCommandPath -Action stop -Component all -WorkspaceWin $WorkspaceWin -WorkspaceWsl $WorkspaceWsl -PidDir $PidDir -LogDir $LogDir
            & $PSCommandPath -Action start -Component all -WorkspaceWin $WorkspaceWin -WorkspaceWsl $WorkspaceWsl -LlamaCppPath $LlamaCppPath -ModelPath $ModelPath -AvatarModelWsl $AvatarModelWsl -AvatarId $AvatarId -AvatarPythonWsl $AvatarPythonWsl -ConfigWsl $ConfigWsl -LlamaSlotProfile $LlamaSlotProfile -LlamaBatchSize $LlamaBatchSize -LlamaUbatchSize $LlamaUbatchSize -LlamaDisableContBatching:$LlamaDisableContBatching -LlamaNoHost:$LlamaNoHost -ReclaimWslCache:$ReclaimWslCache -TtsProfile $TtsProfile -TtsFallbackActive:$TtsFallbackActive -CosyVoicePythonWsl $CosyVoicePythonWsl -FirstPlayableMinChars $FirstPlayableMinChars -PidDir $PidDir -LogDir $LogDir -OfflineStrict:$OfflineStrict
        } else {
            & $PSCommandPath -Action recover -Component $Component -Force -WorkspaceWin $WorkspaceWin -WorkspaceWsl $WorkspaceWsl -LlamaCppPath $LlamaCppPath -ModelPath $ModelPath -AvatarModelWsl $AvatarModelWsl -AvatarId $AvatarId -AvatarPythonWsl $AvatarPythonWsl -ConfigWsl $ConfigWsl -LlamaSlotProfile $LlamaSlotProfile -LlamaBatchSize $LlamaBatchSize -LlamaUbatchSize $LlamaUbatchSize -LlamaDisableContBatching:$LlamaDisableContBatching -LlamaNoHost:$LlamaNoHost -ReclaimWslCache:$ReclaimWslCache -TtsProfile $TtsProfile -TtsFallbackActive:$TtsFallbackActive -CosyVoicePythonWsl $CosyVoicePythonWsl -FirstPlayableMinChars $FirstPlayableMinChars -PidDir $PidDir -LogDir $LogDir -OfflineStrict:$OfflineStrict
        }
    }
}
