<# B5.5 fixed AC-14 release acceptance entrypoint. #>
[CmdletBinding()]
param(
    [ValidateRange(1, 1440)][double]$Minutes = 60,
    [ValidateRange(1, 1000)][int]$CompleteTurns = 20,
    [ValidateRange(1, 1000)][int]$Interrupts = 10,
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$EvidenceWsl = 'audit/v1/B5/B5.5-AC14-soak'
)

$ErrorActionPreference = 'Stop'
$launcher = Join-Path $WorkspaceWin 'ops\windows\RuntimeLauncher.ps1'
$evidenceWin = Join-Path $WorkspaceWin ($EvidenceWsl -replace '/', '\')
New-Item -ItemType Directory -Force -Path $evidenceWin | Out-Null
Write-Host "[release] evidence=$EvidenceWsl minutes=$Minutes complete=$CompleteTurns interrupts=$Interrupts"

function Invoke-Launcher([string]$Action, [string]$Component = 'all', [switch]$Force) {
    # This script already runs in Windows PowerShell. Direct invocation avoids a
    # second WSL interop console process whose parent can detach with exit 255.
    if ($Force) {
        & $launcher -Action $Action -Component $Component -Force
    } else {
        & $launcher -Action $Action -Component $Component
    }
}

function Wait-ResourceHeadroom([int]$TimeoutSec = 180) {
    $samples = @()
    $consecutiveReady = 0
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    do {
        $os = Get-CimInstance Win32_OperatingSystem
        $windowsAvailable = [math]::Round($os.FreePhysicalMemory / 1024, 3)
        $memLine = (& wsl.exe cat /proc/meminfo | Where-Object { $_ -like 'MemAvailable:*' } | Select-Object -First 1)
        if (-not $memLine) { throw 'unable to read WSL MemAvailable' }
        $wslAvailable = [math]::Round(([double](($memLine -split '\s+')[1])) / 1024, 3)
        $ready = ($windowsAvailable -ge 3072 -and $wslAvailable -ge 3072)
        if ($ready) { $consecutiveReady++ } else { $consecutiveReady = 0 }
        $samples += [pscustomobject][ordered]@{
            elapsed_s = [math]::Round($watch.Elapsed.TotalSeconds, 3)
            windows_available_mb = $windowsAvailable
            wsl_available_mb = $wslAvailable
            ready = $ready
            consecutive_ready = $consecutiveReady
        }
        $samples | ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 (Join-Path $evidenceWin 'startup-headroom.json')
        if ($consecutiveReady -ge 3) { return }
        Start-Sleep -Seconds 5
    } while ($watch.Elapsed.TotalSeconds -lt $TimeoutSec)
    throw "resource headroom did not remain at or above 3 GiB per side for three samples within ${TimeoutSec}s"
}

$result = [ordered]@{
    schema_version = 1
    minutes = $Minutes
    repeated_start_same_records = $false
    soak_exit_code = $null
    avatar_recovery_completed = $false
    avatar_pid_before_recovery = $null
    avatar_pid_after_recovery = $null
    non_avatar_pids_unchanged = $false
    stop_attempts = @()
    error = $null
    open_managed_ports_after_stop = @()
    pid_record_count_after_stop = $null
    pass = $false
}

try {
    Invoke-Launcher start
    $first = Get-Content -Raw "$env:LOCALAPPDATA\cyberWife\pid\*.json" | Out-String
    Invoke-Launcher start
    $second = Get-Content -Raw "$env:LOCALAPPDATA\cyberWife\pid\*.json" | Out-String
    if ($first -ne $second) { throw 'second start changed managed PID records' }
    $result.repeated_start_same_records = $true
    Invoke-Launcher status
    Wait-ResourceHeadroom

    & wsl.exe --cd $WorkspaceWsl env PYTHONPATH=backend:. /home/administrator/.cyberWife/venvs/cosyvoice/bin/python -m tests.b3.accept_soak --minutes $Minutes --min-turns $CompleteTurns --interrupts $Interrupts --evidence $EvidenceWsl
    $result.soak_exit_code = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'AC-14 soak failed' }

    $beforeRecovery = Get-Content -Raw "$env:LOCALAPPDATA\cyberWife\pid\*.json" | ConvertFrom-Json
    $beforeByName = @{}
    foreach ($record in $beforeRecovery) { $beforeByName[$record.name] = [int]$record.pid }
    $result.avatar_pid_before_recovery = $beforeByName['avatar']
    Invoke-Launcher recover avatar -Force
    $afterRecovery = Get-Content -Raw "$env:LOCALAPPDATA\cyberWife\pid\*.json" | ConvertFrom-Json
    $afterByName = @{}
    foreach ($record in $afterRecovery) { $afterByName[$record.name] = [int]$record.pid }
    $result.avatar_pid_after_recovery = $afterByName['avatar']
    if ($result.avatar_pid_before_recovery -eq $result.avatar_pid_after_recovery) {
        throw 'forced avatar recovery did not replace the avatar PID'
    }
    $result.non_avatar_pids_unchanged = (
        $beforeByName['llama'] -eq $afterByName['llama'] -and
        $beforeByName['speech'] -eq $afterByName['speech'] -and
        $beforeByName['gateway'] -eq $afterByName['gateway']
    )
    if (-not $result.non_avatar_pids_unchanged) { throw 'avatar recovery changed a healthy non-avatar PID' }
    $result.avatar_recovery_completed = $true
} catch {
    $result.error = $_.Exception.Message
} finally {
    $stopResults = @()
    for ($attempt = 1; $attempt -le 2; $attempt++) {
        try {
            Invoke-Launcher stop
            $stopResults += [pscustomobject][ordered]@{ attempt = $attempt; pass = $true; error = $null }
        } catch {
            $stopResults += [pscustomobject][ordered]@{ attempt = $attempt; pass = $false; error = $_.Exception.Message }
        }
    }
    $result.stop_attempts = $stopResults
    $ports = @(7860, 8010, 8011, 8090, 8091)
    $open = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort })
    $pidFiles = @(Get-ChildItem "$env:LOCALAPPDATA\cyberWife\pid\*.json" -ErrorAction SilentlyContinue)
    $result.open_managed_ports_after_stop = @($open | ForEach-Object LocalPort)
    $result.pid_record_count_after_stop = $pidFiles.Count
    $stopsPassed = (@($stopResults | Where-Object { -not $_.pass }).Count -eq 0)
    $result.pass = (
        $null -eq $result.error -and
        $result.soak_exit_code -eq 0 -and
        $result.repeated_start_same_records -and
        $result.avatar_recovery_completed -and
        $result.non_avatar_pids_unchanged -and
        $stopsPassed -and
        $open.Count -eq 0 -and
        $pidFiles.Count -eq 0
    )
    $result | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $evidenceWin 'lifecycle.json')
    $result | ConvertTo-Json -Depth 5
}
if (-not $result.pass) { exit 2 }
