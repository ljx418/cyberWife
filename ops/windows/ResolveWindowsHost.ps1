<#
.SYNOPSIS
  解析 WSL2 → Windows 主机 IP（首选 wsl hostname -I，备用 Windows 网卡 CIM）。

.DESCRIPTION
  M1 阶段：实现-contracts.md §9 跨边界解析合同。
  1. 通过 wsl hostname -I 取 WSL 视角的 Windows 主机 IP（首选）
  2. 备用：Get-CimInstance Win32_NetworkAdapterConfiguration | IPEnabled | 取第一个 IPv4
  3. 写入 config/runtime.local.toml 的 gateway.windows_llama_host 字段
  4. 通过 httpx 异步客户端验证 :8090 可达性（PS 等价用 Invoke-WebRequest）
  5. 失败：连续 3 次进入 error；RuntimeLauncher 阻断启动

.EXAMPLE
  .\ResolveWindowsHost.ps1
  .\ResolveWindowsHost.ps1 -WslDistro Ubuntu-22.04 -DryRun
#>

[CmdletBinding()]
param(
    [string]$WslDistro = '',
    [int]$ProbePort = 8090,
    [int]$MaxRetries = 3,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Get-WslGateway {
    # wsl hostname -I 在 WSL 内部执行；先 wsl.exe（Windows 端），再 fallback 到当前主机网络
    try {
        $wslOut = wsl.exe hostname -I 2>$null
        if ($LASTEXITCODE -eq 0 -and $wslOut) {
            $ips = ($wslOut -split '\s+') | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' }
            if ($ips) { return $ips[0] }
        }
    } catch {}
    # 备用：从 Windows 网卡取 IPv4
    $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=$true" -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -and $_.IPAddress[0] -notmatch '^169\.254\.' -and $_.IPAddress[0] -ne '127.0.0.1' } |
        Select-Object -First 1
    if ($adapter -and $adapter.IPAddress) { return $adapter.IPAddress[0] }
    return $null
}

function Test-Reachable {
    param([string]$Host, [int]$Port)
    try {
        $r = Invoke-WebRequest -Uri "http://$Host`:$Port/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return ($r.StatusCode -in @(200, 404))  # 404 也算可达（路由在但 /health 路径不对）
    } catch {
        return $false
    }
}

$host_ip = Get-WslGateway
if (-not $host_ip) {
    throw "ResolveWindowsHost: failed to obtain Windows host IP after wsl + CIM fallbacks"
}

Write-Host "[ResolveWindowsHost] windows_host_ip = $host_ip"

if ($DryRun) {
    Write-Host "[ResolveWindowsHost] --DryRun: would write config/runtime.local.toml gateway.windows_llama_host=$host_ip"
    return
}

# 写入 config/runtime.local.toml（Git ignore）
$repoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
$configDir = Join-Path $repoRoot 'config'
if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Force -Path $configDir | Out-Null }
$runtimeLocal = Join-Path $configDir 'runtime.local.toml'

$content = @"
# cyberWife V1 runtime.local.toml（本机私有，Git ignore）
# 由 ops/windows/ResolveWindowsHost.ps1 在启动时生成
generated_at = "$((Get-Date).ToString('o'))"

[gateway]
windows_llama_host = "$host_ip"

[probe]
host = "$host_ip"
port = $ProbePort
"@
Set-Content -Path $runtimeLocal -Value $content -Encoding UTF8
Write-Host "[ResolveWindowsHost] wrote $runtimeLocal"

# 可达性验证（连续 3 次失败阻断）
$ok = $false
for ($i = 0; $i -lt $MaxRetries; $i++) {
    if (Test-Reachable $host_ip $ProbePort) { $ok = $true; break }
    Write-Host "[ResolveWindowsHost] probe $host_ip`:$ProbePort retry $(( $i + 1 ))/$MaxRetries failed"
    Start-Sleep -Seconds 2
}
if (-not $ok) {
    throw "ResolveWindowsHost: $host_ip`:$ProbePort not reachable after $MaxRetries retries; RuntimeLauncher will block"
}
Write-Host "[ResolveWindowsHost] probe OK $host_ip`:$ProbePort"
