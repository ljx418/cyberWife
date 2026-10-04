[CmdletBinding()]
param(
    [string]$PidRecord = "$env:LOCALAPPDATA\cyberWife\pid\avatar.json",
    [string]$Health = "http://127.0.0.1:8010/health"
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $PidRecord)) { throw "owned Avatar PID record is missing" }
$record = Get-Content -Raw -LiteralPath $PidRecord | ConvertFrom-Json
if ($record.name -ne 'avatar' -or $record.marker -ne 'app.py --bind 127.0.0.1') {
    throw "Avatar PID record ownership marker is invalid"
}
$process = Get-CimInstance Win32_Process -Filter "ProcessId=$($record.pid)" -ErrorAction Stop
if (-not (($process.CommandLine -as [string]) -like "*$($record.marker)*")) {
    throw "refusing to stop PID $($record.pid): command marker mismatch"
}
$requestedAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
Stop-Process -Id ([int]$record.pid) -Force -ErrorAction Stop
$offlineAt = $null
for ($i = 0; $i -lt 40; $i++) {
    try {
        Invoke-WebRequest -Uri $Health -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop | Out-Null
    } catch {
        $offlineAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
        break
    }
    Start-Sleep -Milliseconds 50
}
if ($null -eq $offlineAt) { throw "Avatar endpoint remained healthy after owned process termination" }
[ordered]@{
    pid = [int]$record.pid
    marker_validated = $true
    requested_at_ms = $requestedAt
    offline_at_ms = $offlineAt
} | ConvertTo-Json -Compress

