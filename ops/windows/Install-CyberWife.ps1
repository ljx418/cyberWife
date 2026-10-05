<# Safe, idempotent installation readiness and local configuration entrypoint. #>
[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [ValidateSet('audit', 'prepare', 'verify')]
    [string]$Action = 'audit',
    [ValidateSet('none', 'wheelhouse', 'online')]
    [string]$DependencyMode = 'none',
    [switch]$AllowNetworkInstall,
    [string]$WheelhouseWsl = '',
    [string]$WorkspaceWin = 'C:\workSpace\cyberWife',
    [string]$WorkspaceWsl = '/mnt/c/workSpace/cyberWife',
    [string]$WslHome = '',
    [string]$PythonWsl = 'python3',
    [string]$LlamaCppPath = 'C:\tools\llama.cpp\llama-server.exe',
    [string]$LlamaModelPath = 'C:\ComfyUI-aki-v2\ComfyUI\models\LLM\Qwen3-14B-Q4_K_M.gguf',
    [string]$AvatarModelWsl = '/mnt/c/ComfyUI-aki-v2/ComfyUI/models/Audio/wav2lip/wav2lip.pth',
    [string]$ComfyRootWsl = '/mnt/c/ComfyUI-aki-v2/ComfyUI',
    [string]$ArtifactManifestWsl = '',
    [switch]$SkipFrontendBuild,
    [string]$ReportPath = ''
)

$ErrorActionPreference = 'Stop'
$checks = [System.Collections.Generic.List[object]]::new()

function Add-Check([string]$Name, [bool]$Pass, [string]$Detail, [bool]$Required = $true) {
    $checks.Add([pscustomobject][ordered]@{ name = $Name; pass = $Pass; required = $Required; detail = $Detail })
}

function Test-WslPath([string]$Path, [string]$Kind = 'e') {
    & wsl.exe -- test "-$Kind" $Path
    return ($LASTEXITCODE -eq 0)
}

function Invoke-Wsl([string[]]$Arguments) {
    & wsl.exe -- @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WSL command failed: $($Arguments -join ' ')" }
}

function Test-WslPython([string]$Python, [string[]]$Modules) {
    if (-not (Test-WslPath $Python 'x')) { return $false }
    $code = "import " + ($Modules -join ',')
    & wsl.exe -- $Python -c $code 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Get-WslCommandPath([string]$Name) {
    $resolved = ((& wsl.exe -- which $Name 2>$null) | Out-String).Trim()
    if ($LASTEXITCODE -eq 0 -and $resolved.StartsWith('/')) { return $resolved }
    foreach ($candidate in @("$actualWslHome/.local/bin/$Name", "/usr/local/bin/$Name")) {
        if ($actualWslHome -and (Test-WslPath $candidate 'x')) { return $candidate }
    }
    return ''
}

function Test-WslVenv([string]$Venv) {
    $python = "$Venv/bin/python"
    if (-not (Test-WslPath $python 'x')) { return $false }
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & wsl.exe -- $python -c 'import pathlib,pip,sys; cfg=pathlib.Path(sys.prefix,"pyvenv.cfg").read_text().lower(); raise SystemExit(0 if sys.version_info[:2] == (3,12) and "include-system-site-packages = false" in cfg else 1)' 2>$null
    $probeExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    return ($probeExit -eq 0)
}

function New-WslVenv([string]$Venv) {
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & wsl.exe -- $PythonWsl -m venv --clear $Venv 2>$null
    $venvExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($venvExit -eq 0 -and (Test-WslPath "$Venv/bin/python" 'x')) { return }
    $uv = Get-WslCommandPath 'uv'
    if ($uv) {
        $pythonPath = Get-WslCommandPath $PythonWsl
        if (-not $pythonPath) { throw "cannot resolve WSL Python: $PythonWsl" }
        Invoke-Wsl @($uv, 'venv', '--clear', '--seed', '--python', $pythonPath, $Venv)
        return
    }
    $virtualenv = Get-WslCommandPath 'virtualenv'
    if ($virtualenv) {
        Invoke-Wsl @($virtualenv, '--clear', '--python', $PythonWsl, $Venv)
        return
    }
    throw 'cannot create WSL venv; install python3.12-venv, uv, or virtualenv explicitly'
}

function Install-WslRuntime([string]$Venv, [string]$Requirements, [string]$Component) {
    $python = "$Venv/bin/python"
    if (-not (Test-WslVenv $Venv)) {
        New-WslVenv $Venv
    }
    if ($DependencyMode -eq 'wheelhouse') {
        if (-not $WheelhouseWsl -or -not (Test-WslPath $WheelhouseWsl 'd')) {
            throw 'DependencyMode=wheelhouse requires an existing -WheelhouseWsl directory'
        }
        $componentWheelhouse = "$WheelhouseWsl/$Component"
        $packageRoot = if (Test-WslPath $componentWheelhouse 'd') { $componentWheelhouse } else { $WheelhouseWsl }
        Invoke-Wsl @($python, '-m', 'pip', 'install', '--no-index', '--find-links', $packageRoot, '-r', $Requirements)
    } elseif ($DependencyMode -eq 'online') {
        if (-not $AllowNetworkInstall) {
            throw 'DependencyMode=online requires explicit -AllowNetworkInstall'
        }
        Invoke-Wsl @($python, '-m', 'pip', 'install', '-r', $Requirements)
    }
    Invoke-Wsl @($python, '-m', 'pip', 'check')
}

$wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
$actualWslHome = ''
if ($wslCommand) {
    $actualWslHome = ((& wsl.exe -- sh -lc 'printf %s "$HOME"') | Out-String).Trim()
    if ([string]::IsNullOrWhiteSpace($WslHome)) { $WslHome = $actualWslHome }
}
$dataRoot = if ($WslHome) { "$WslHome/.cyberWife" } else { '' }
$coreVenv = "$dataRoot/venvs/cosyvoice"
$avatarVenv = "$dataRoot/venvs/avatar-v1-py312"
$coreRequirements = "$WorkspaceWsl/backend/requirements-runtime-core-cu128.txt"
$avatarRequirements = "$WorkspaceWsl/workers/avatar/requirements-runtime-cu128.txt"

if ($Action -eq 'prepare') {
    if (-not $wslCommand -or -not $WslHome) { throw 'cannot prepare without a resolved WSL home' }
    if ($PSCmdlet.ShouldProcess($dataRoot, 'create private runtime directories')) {
        Invoke-Wsl @('mkdir', '-p', "$dataRoot/assets/portrait", "$dataRoot/assets/voice", "$dataRoot/logs", "$dataRoot/audit", "$dataRoot/avatar/avatars", "$dataRoot/venvs")
        Invoke-Wsl @('chmod', '700', $dataRoot, "$dataRoot/assets", "$dataRoot/logs", "$dataRoot/audit", "$dataRoot/avatar")
    }
    $runtimeConfig = Join-Path $WorkspaceWin 'config\runtime.local.toml'
    if (-not (Test-Path -LiteralPath $runtimeConfig)) {
        $content = @"
# Generated by Install-CyberWife.ps1; private local paths only.
[paths]
assets_root = "$dataRoot/assets"
data_root = "$dataRoot"
logs_root = "$dataRoot/logs"
salt_file = "$dataRoot/audit/.salt"
cosyvoice_source = "$dataRoot/src/CosyVoice"

[bootstrap]
manifest = "$dataRoot/bootstrap/manifest.json"

[db]
path = "$dataRoot/cyberwife.db"
wal = true
cache_size_kb = 2048
synchronous = "NORMAL"

[models]
tts = "cosyvoice2-0.5b"
"@
        if ($PSCmdlet.ShouldProcess($runtimeConfig, 'create missing runtime config')) {
            Set-Content -LiteralPath $runtimeConfig -Value $content -Encoding UTF8 -NoNewline
        }
    }
    if ($DependencyMode -ne 'none' -and $PSCmdlet.ShouldProcess($dataRoot, "install $DependencyMode Python dependencies")) {
        if (-not (Test-WslPath $coreRequirements 'f') -or -not (Test-WslPath $avatarRequirements 'f')) {
            throw 'project runtime requirement files are missing'
        }
        if ($DependencyMode -eq 'wheelhouse' -and (Test-WslPath "$WheelhouseWsl/core" 'd')) {
            $manifestTool = "$WorkspaceWsl/ops/acceptance/wheelhouse_manifest.py"
            if (-not (Test-WslPath "$WheelhouseWsl/wheelhouse-manifest.json" 'f')) {
                throw 'component wheelhouse requires wheelhouse-manifest.json'
            }
            Invoke-Wsl @($PythonWsl, $manifestTool, 'verify', '--root', $WheelhouseWsl)
        }
        Install-WslRuntime $coreVenv $coreRequirements 'core'
        Install-WslRuntime $avatarVenv $avatarRequirements 'avatar'
    }
    if ($ArtifactManifestWsl -and $PSCmdlet.ShouldProcess($dataRoot, 'validate and publish offline local artifacts')) {
        if (-not (Test-WslPath $ArtifactManifestWsl 'f')) { throw 'ArtifactManifestWsl does not exist' }
        $artifactPython = if (Test-WslPath "$coreVenv/bin/python" 'x') { "$coreVenv/bin/python" } else { $PythonWsl }
        Invoke-Wsl @(
            $artifactPython, "$WorkspaceWsl/ops/acceptance/prepare_local_artifacts.py", 'prepare',
            '--manifest', $ArtifactManifestWsl,
            '--repo-root', $WorkspaceWsl,
            '--data-root', $dataRoot,
            '--report', "$dataRoot/audit/local-artifacts.json"
        )
    }
    $frontendIndex = Join-Path $WorkspaceWin 'prototype\dist\index.html'
    if (-not $SkipFrontendBuild -and -not (Test-Path -LiteralPath $frontendIndex)) {
        if ($DependencyMode -ne 'online' -or -not $AllowNetworkInstall) {
            throw 'production frontend is missing; offline prepare never runs npm ci (restore the tracked prototype/dist release)'
        }
        $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
        if (-not $npm) { throw 'npm.cmd is required to build the missing frontend release' }
        if ($PSCmdlet.ShouldProcess((Join-Path $WorkspaceWin 'prototype'), 'build production frontend')) {
            & npm.cmd --prefix (Join-Path $WorkspaceWin 'prototype') ci
            if ($LASTEXITCODE -ne 0) { throw 'frontend npm ci failed' }
            & npm.cmd --prefix (Join-Path $WorkspaceWin 'prototype') run build
            if ($LASTEXITCODE -ne 0) { throw 'frontend production build failed' }
        }
    }
}

Add-Check 'windows.wsl' ($null -ne $wslCommand) 'wsl.exe must be installed and callable'
Add-Check 'wsl.home' (-not [string]::IsNullOrWhiteSpace($WslHome) -and $WslHome.StartsWith('/')) $WslHome
Add-Check 'windows.workspace' (Test-Path -LiteralPath $WorkspaceWin -PathType Container) $WorkspaceWin
Add-Check 'windows.llama_binary' (Test-Path -LiteralPath $LlamaCppPath -PathType Leaf) $LlamaCppPath
Add-Check 'windows.llama_model' (Test-Path -LiteralPath $LlamaModelPath -PathType Leaf) $LlamaModelPath
Add-Check 'windows.nvidia_smi' ($null -ne (Get-Command nvidia-smi.exe -ErrorAction SilentlyContinue)) 'NVIDIA driver CLI'

if ($wslCommand -and $WslHome) {
    Add-Check 'wsl.workspace' (Test-WslPath $WorkspaceWsl 'd') $WorkspaceWsl
    Add-Check 'wsl.core_python' (Test-WslPath "$coreVenv/bin/python" 'x') "$coreVenv/bin/python"
    Add-Check 'wsl.avatar_python' (Test-WslPath "$avatarVenv/bin/python" 'x') "$avatarVenv/bin/python"
    Add-Check 'wsl.cosy_source' (Test-WslPath "$dataRoot/src/CosyVoice" 'd') "$dataRoot/src/CosyVoice"
    Add-Check 'wsl.avatar_model' (Test-WslPath $AvatarModelWsl 'f') $AvatarModelWsl
    Add-Check 'release.frontend' (Test-WslPath "$WorkspaceWsl/prototype/dist/index.html" 'f') "$WorkspaceWsl/prototype/dist/index.html"
    Add-Check 'release.model_registry' (Test-WslPath "$WorkspaceWsl/config/model-registry.local.yaml" 'f') "$WorkspaceWsl/config/model-registry.local.yaml"
    if ($ArtifactManifestWsl) {
        $artifactPython = if (Test-WslPath "$coreVenv/bin/python" 'x') { "$coreVenv/bin/python" } else { $PythonWsl }
        $savedPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & wsl.exe -- $artifactPython "$WorkspaceWsl/ops/acceptance/prepare_local_artifacts.py" verify --repo-root $WorkspaceWsl --data-root $dataRoot --report "$dataRoot/audit/local-artifacts.json" 2>$null
        $artifactExit = $LASTEXITCODE
        $ErrorActionPreference = $savedPreference
        Add-Check 'release.local_artifacts' ($artifactExit -eq 0) "$dataRoot/bootstrap/manifest.json"
    }
    Add-Check 'release.avatar_workflows' ((Test-WslPath "$WorkspaceWsl/ops/comfy_avatar_frontalize_api.json" 'f') -and (Test-WslPath "$WorkspaceWsl/ops/comfy_avatar_idle_api.json" 'f')) 'frontal + idle API workflows'
    $comfyFiles = @(
        'main.py',
        'models/diffusion_models/qwen-image-2.1-Q6_K.gguf',
        'models/text_encoders/qwen3vl_8b_bf16.safetensors',
        'models/vae/qwen_image_2.1_vae_bf16.safetensors',
        'models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors',
        'models/vae/wan_2.1_vae.safetensors',
        'models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors',
        'models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors',
        'models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_high_noise.safetensors',
        'models/loras/wan2.2_i2v_lightx2v_4steps_lora_v1_low_noise.safetensors'
    )
    $missingComfy = @($comfyFiles | Where-Object { -not (Test-WslPath "$ComfyRootWsl/$_" 'f') })
    $comfyDetail = if ($missingComfy.Count) { $missingComfy -join ',' } else { 'all local files present' }
    Add-Check 'comfy.avatar_pipeline' ($missingComfy.Count -eq 0) $comfyDetail
    if ($Action -eq 'verify') {
        Add-Check 'wsl.core_imports' (Test-WslPython "$coreVenv/bin/python" @('fastapi','uvicorn','torch','torchaudio','faster_whisper','sentence_transformers','silero_vad','transformers','onnxruntime')) 'gateway + speech + CosyVoice imports'
        Add-Check 'wsl.avatar_imports' (Test-WslPython "$avatarVenv/bin/python" @('torch','cv2','aiortc','flask','numpy')) 'LiveTalking/Wav2Lip imports'
    }
}

$requiredFailures = @($checks | Where-Object { $_.required -and -not $_.pass })
$result = [pscustomobject][ordered]@{
    schema_version = 2
    action = $Action
    dependency_mode = $DependencyMode
    workspace_windows = $WorkspaceWin
    workspace_wsl = $WorkspaceWsl
    wsl_home = $WslHome
    data_root_wsl = $dataRoot
    checks = @($checks)
    required_failure_count = $requiredFailures.Count
    ready = ($requiredFailures.Count -eq 0)
}
if ($ReportPath) {
    $parent = Split-Path -Parent $ReportPath
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}
$result | ConvertTo-Json -Depth 6
if (-not $result.ready) { exit 2 }
