<#
.SYNOPSIS
  Windows llama-server.exe 包装；幂等启动 + 健康探测。

.DESCRIPTION
  把 Windows 上的 llama.cpp CUDA 12.4 二进制（已落到 C:\tools\llama.cpp\）按
  config/default.example.toml [server] 与 [models] 段启动，并通过 /health 端点
  探测 readiness。M1 阶段默认 30s 内未 ready 即报错。

.PARAMETER ModelPath    GGUF 权重绝对路径
.PARAMETER LlamaCppPath llama-server.exe 路径
.PARAMETER Host         bind 地址（默认 127.0.0.1）
.PARAMETER Port         端口（默认 8090）
.PARAMETER CtxSize      context size tokens（默认 8192）
.PARAMETER GpuLayers    GPU offload 层数（默认 40 = 全 GPU）
.PARAMETER TimeoutSec   ready 探测超时

.EXAMPLE
  .\StartLlamaCpp.ps1 -ModelPath 'C:\ComfyUI-aki-v2\ComfyUI\models\LLM\Qwen3-14B-Q4_K_M.gguf'
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ModelPath,
    [string]$LlamaCppPath = 'C:\tools\llama.cpp\llama-server.exe',
    [string]$Host = '127.0.0.1',
    [int]$Port = 8090,
    [int]$CtxSize = 8192,
    [int]$GpuLayers = 40,
    [int]$TimeoutSec = 30
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $LlamaCppPath)) {
    throw "llama-server.exe not found at $LlamaCppPath (run install/llama-cpp-install.ps1 first)"
}
if (-not (Test-Path $ModelPath)) {
    throw "model file not found at $ModelPath"
}

# 端口占用检查
$existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[StartLlamaCpp] port $Port already in use (PID=$($existing.OwningProcess)); skipping start"
    exit 0
}

$logDir = "$env:LOCALAPPDATA\cyberWife\logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }
$stdout = Join-Path $logDir 'llama-server.log'
$stderr = Join-Path $logDir 'llama-server.err.log'

$args = @(
    '-m', $ModelPath,
    '--host', $Host,
    '--port', $Port,
    '-c', $CtxSize,
    '--n-gpu-layers', $GpuLayers
)

Write-Host "[StartLlamaCpp] launching: $LlamaCppPath $($args -join ' ')"
$proc = Start-Process -FilePath $LlamaCppPath -ArgumentList $args -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -NoNewWindow

$pidDir = "$env:LOCALAPPDATA\cyberWife\pid"
if (-not (Test-Path $pidDir)) { New-Item -ItemType Directory -Force -Path $pidDir | Out-Null }
Set-Content -Path (Join-Path $pidDir 'llama-server.pid') -Value $proc.Id

# 等待 ready
$ready = $false
for ($i = 0; $i -lt $TimeoutSec; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://$Host`:$Port/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if (-not $ready) {
    Write-Host "[StartLlamaCpp] llama-server failed to become ready after ${TimeoutSec}s"
    if (Test-Path $stderr) { Write-Host "--- last 30 lines of stderr ---"; Get-Content $stderr -Tail 30 }
    throw "llama-server not ready"
}

Write-Host "[StartLlamaCpp] llama-server ready PID=$($proc.Id) http://$Host`:$Port"
