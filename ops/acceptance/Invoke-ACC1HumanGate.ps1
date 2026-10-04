<# Guided, human-observed accessibility and physical-microphone acceptance. #>
[CmdletBinding()]
param(
    [switch]$AcceptFocusChange,
    [string]$Operator = '',
    [string]$Url = 'http://127.0.0.1:7860',
    [string]$ChromePath = 'C:\Program Files\Google\Chrome\Application\chrome.exe',
    [string]$ReportPath = 'C:\workSpace\cyberWife\audit\v1\ACC1\human-gate.json'
)

$ErrorActionPreference = 'Stop'
if (-not $AcceptFocusChange) {
    throw 'This guided gate opens Chrome and Narrator and will take focus. Re-run with -AcceptFocusChange when ready.'
}
if ([string]::IsNullOrWhiteSpace($Operator)) { throw '-Operator is required for attributable human evidence' }
if (-not (Test-Path -LiteralPath $ChromePath -PathType Leaf)) { throw "Chrome missing: $ChromePath" }
$narratorPath = Join-Path $env:WINDIR 'System32\Narrator.exe'
if (-not (Test-Path -LiteralPath $narratorPath -PathType Leaf)) { throw "Narrator missing: $narratorPath" }

$healthUris = @(
    'http://127.0.0.1:8090/health',
    'http://127.0.0.1:8091/health',
    'http://127.0.0.1:8010/health',
    'http://127.0.0.1:8011/healthz',
    'http://127.0.0.1:7860/api/v1/health'
)
foreach ($uri in $healthUris) {
    try { $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 3 }
    catch { throw "Runtime must already be healthy before ACC1: $uri" }
    if ($response.StatusCode -ne 200) { throw "Runtime health failed: $uri" }
}

$audioEndpoints = @(
    Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction SilentlyContinue |
        ForEach-Object { $_.FriendlyName } |
        Where-Object { $_ }
)
if ($audioEndpoints.Count -eq 0) { throw 'No enabled Windows audio endpoint was found' }

function Read-Pass([string]$Prompt) {
    do { $answer = (Read-Host "$Prompt [y/n]").Trim().ToLowerInvariant() } while ($answer -notin @('y', 'n'))
    return ($answer -eq 'y')
}

$profile = Join-Path $env:TEMP ("cyberwife-acc1-" + [guid]::NewGuid().ToString('N'))
$narratorWasRunning = $null -ne (Get-Process Narrator -ErrorAction SilentlyContinue)
$startedNarrator = $false
$answers = [ordered]@{}
try {
    if (-not $narratorWasRunning) {
        Start-Process -FilePath $narratorPath | Out-Null
        $startedNarrator = $true
    }
    New-Item -ItemType Directory -Path $profile | Out-Null
    Start-Process -FilePath $ChromePath -ArgumentList @(
        "--user-data-dir=$profile", '--new-window', '--no-first-run', $Url
    ) | Out-Null
    Write-Host 'Chrome/Narrator are open. Grant microphone permission only to the loopback page, then complete each task.'
    $answers.screen_reader_settings = Read-Pass '读屏可独立打开设置并识别关闭按钮'
    $answers.screen_reader_start = Read-Pass '读屏可启动对话并听到状态变化'
    $answers.screen_reader_interrupt = Read-Pass '读屏可理解打断操作与恢复状态'
    $answers.screen_reader_persona = Read-Pass '读屏可编辑并保存人设'
    $answers.screen_reader_delete = Read-Pass '读屏可理解删除确认框并取消/确认'
    $answers.physical_mic_three_turns = Read-Pass '实体麦克风连续3轮均有ASR final、可听回复和人物画面'
    $answers.physical_mic_barge_in = Read-Pass '说话期间打断1次，旧轮音频/画面泄漏为0'
} finally {
    Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" -ErrorAction SilentlyContinue |
        Where-Object { ($_.CommandLine -as [string]) -like "*$profile*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    if ($startedNarrator) { Stop-Process -Name Narrator -Force -ErrorAction SilentlyContinue }
}

$passed = @($answers.Values | Where-Object { -not $_ }).Count -eq 0
$result = [ordered]@{
    schema_version = 1
    gate = 'ACC1-human-screen-reader-physical-mic'
    completed_at = (Get-Date -Format 'o')
    operator = $Operator
    screen_reader = 'Windows Narrator'
    audio_endpoints = $audioEndpoints
    stores_raw_audio = $false
    answers = $answers
    result = if ($passed) { 'PASS' } else { 'FAIL' }
}
$parent = Split-Path -Parent $ReportPath
if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
$result | ConvertTo-Json -Depth 6
if (-not $passed) { exit 2 }
