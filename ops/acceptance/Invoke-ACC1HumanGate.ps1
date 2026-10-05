<# Guided human perception plus machine-bound physical-microphone acceptance. #>
[CmdletBinding()]
param(
    [switch]$AcceptFocusChange,
    [string]$Operator = '',
    [string]$Url = 'http://127.0.0.1:7860',
    [string]$ChromePath = 'C:\Program Files\Google\Chrome\Application\chrome.exe',
    [string]$ReportPath = 'C:\workSpace\cyberWife\audit\v1\ACC1\human-gate.json'
)

$ErrorActionPreference = 'Stop'
$stores_raw_audio = $false
if (-not $AcceptFocusChange) {
    throw 'This guided gate opens Chrome and Narrator and will take focus. Re-run with -AcceptFocusChange when ready.'
}
if ([string]::IsNullOrWhiteSpace($Operator)) { throw '-Operator is required for attributable human evidence' }
if (-not (Test-Path -LiteralPath $ChromePath -PathType Leaf)) { throw "Chrome missing: $ChromePath" }
$narratorPath = Join-Path $env:WINDIR 'System32\Narrator.exe'
if (-not (Test-Path -LiteralPath $narratorPath -PathType Leaf)) { throw "Narrator missing: $narratorPath" }
$node = (Get-Command node.exe -ErrorAction SilentlyContinue).Source
if (-not $node) { throw 'Windows node.exe is required for the Playwright evidence collector' }
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$collector = Join-Path $repoRoot 'prototype\tests\acc1_human_gate.mjs'
if (-not (Test-Path -LiteralPath $collector -PathType Leaf)) { throw "Collector missing: $collector" }

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

$narratorWasRunning = $null -ne (Get-Process Narrator -ErrorAction SilentlyContinue)
$startedNarrator = $false
$exitCode = 2
try {
    if (-not $narratorWasRunning) {
        Start-Process -FilePath $narratorPath | Out-Null
        $startedNarrator = $true
    }
    & $node $collector `
        --no-fake-media `
        --operator $Operator `
        --url "$($Url.TrimEnd('/'))/?preview=1" `
        --chrome-path $ChromePath `
        --output $ReportPath
    $exitCode = $LASTEXITCODE
} finally {
    if ($startedNarrator) { Stop-Process -Name Narrator -Force -ErrorAction SilentlyContinue }
}
if ($stores_raw_audio) { throw 'ACC1 collector must never store raw audio' }
exit $exitCode
