# cyberWife V1 安装、验证与数据运维

## 1. 支持范围

Windows 11 + WSL2、NVIDIA RTX 4090级24GiB显卡、宿主32GiB内存。V1不使用Docker。仓库不分发模型、授权照片或声音；准备阶段只接受本机已有的合法工件，不执行静默联网下载。

## 2. 工件位置

- 仓库：默认`C:\workSpace\cyberWife`，可通过参数覆盖。
- llama.cpp：`C:\tools\llama.cpp\llama-server.exe`。
- Qwen3-14B GGUF、Wav2Lip和ComfyUI模型：位置由安装入口参数及模型注册表声明。
- WSL私有根：运行时从当前WSL用户`$HOME/.cyberWife`派生，不固定用户名。
- Core（Gateway/Speech/Cosy）与Avatar隔离venv：`$HOME/.cyberWife/venvs/{cosyvoice,avatar-v1-py312}`；生产Speech不使用系统Python。

## 3. 三步安装入口

在Windows PowerShell执行：

```powershell
cd C:\workSpace\cyberWife
.\ops\windows\Install-CyberWife.ps1 -Action audit
.\ops\windows\Install-CyberWife.ps1 -Action prepare
.\ops\windows\Install-CyberWife.ps1 -Action verify
```

`audit`只读并逐项报告缺失项；`prepare`创建缺失的私有目录和runtime配置，已有配置绝不覆盖，可先加`-WhatIf`演练；`verify`还会真实import Core/Speech/Cosy与Avatar关键模块，并检查动态形象所需的两份工作流和全部ComfyUI本地模型。

从空venv准备依赖时二选一：

```powershell
# 推荐：已审核的本地wheelhouse，全程不出网
.\ops\windows\Install-CyberWife.ps1 -Action prepare -DependencyMode wheelhouse -WheelhouseWsl /path/to/wheels

# 仅在操作者明确允许初次联网安装时
.\ops\windows\Install-CyberWife.ps1 -Action prepare -DependencyMode online -AllowNetworkInstall
```

默认`-DependencyMode none`，不发生依赖下载。在线模式没有`-AllowNetworkInstall`会立即失败；离线模式只从指定wheelhouse解析。两种模式都执行`pip check`。

V1发布仓库直接携带已验收的`prototype/dist`。离线prepare发现该目录缺失或损坏时立即失败并要求恢复Git工件，绝不会静默执行`npm ci`；只有显式`DependencyMode=online + AllowNetworkInstall`才允许重建缺失前端。

### 独立干净环境总验收

先在开发机只读获取两个拒绝哈希（不要把输出提交到Git）：

```powershell
.\ops\acceptance\Invoke-INST1CleanMachineAcceptance.ps1 -Action fingerprint
```

在全新Windows用户与新安装的默认WSL中再次运行`fingerprint`，确认数据根、Core/Avatar venv、`runtime.local.toml`和本机模型注册表五项均为absent。复制`config/local-artifacts.example.json`到仓库外私有位置，填写七个V1实时模型（包含Qwen3-TTS回退）、CosyVoice源码、已授权单声道16-bit PCM WAV及其逐字稿、预构建Avatar目录；路径统一使用WSL绝对路径，逐项复核许可证/同意后才能把`false`改为`true`。然后执行：

```powershell
.\ops\acceptance\Invoke-INST1CleanMachineAcceptance.ps1 `
  -Action accept -AcceptCleanEnvironment `
  -RejectWindowsSidHash "<开发机windows_sid_hash>" `
  -RejectWslMachineIdHash "<开发机wsl_machine_id_hash>" `
  -WheelhouseWsl "/path/to/cu128-py312" `
  -ArtifactManifestWsl "/path/to/local-artifacts.private.json"
```

工具拒绝与开发机相同的Windows用户或相同/克隆的WSL machine-id，且拒绝已有数据根/venv/config/本机注册表。制品准备器先验路径、类型、可选SHA、授权声明和Avatar结构，再生成Git-ignore的模型注册表，把参考音频、Avatar与CosyVoice源码发布到用户私有数据根；审计报告不保存音频逐字稿或绝对私有路径。正式流程只用离线wheelhouse，自动完成prepare、verify、start×2、status、Avatar recover、stop×2；报告位于当前Windows用户的`LocalAppData\cyberWife\acceptance\INST1-AC06.json`。工具不会创建系统用户、安装WSL或驱动，这些高风险系统步骤必须由验收环境管理员预先完成。

创建venv时安装器依次尝试Python标准`venv`、`uv`和`virtualenv`。如三者均不存在，脚本会要求操作者显式安装`python3.12-venv`或其中一个创建器；安装器不自动执行`sudo apt`。

需要准备可重复使用的离线依赖库时，在一次允许联网的维护窗口执行：

```powershell
.\ops\windows\Build-CyberWifeWheelhouse.ps1 -AllowNetworkDownload
.\ops\windows\Install-CyberWife.ps1 -Action prepare -DependencyMode wheelhouse -WheelhouseWsl /home/<WSL用户>/.cyberWife/wheelhouse/cu128-py312
```

构建器分别保存Core与Avatar wheel，生成并验证SHA256清单；安装器在创建venv前再次验证。已有wheelhouse默认不会覆盖，只有显式`-ReplaceExisting`才会先重命名为带时间戳的备份。

安装器不会安装驱动、修改防火墙、下载模型或结束进程。缺少的模型、CosyVoice源码和授权素材必须由操作者按来源/许可证准备后重新verify。

## 4. 照片生成动态形象

首次引导的“人物形象”或“设置 → 人物”已内置完整流程：选择JPG/PNG、调整取景、点击“生成动态形象”。系统会暂停当前占用显存的实时组件，以离线ComfyUI依次生成标准正面照和10秒首尾闭环Idle视频，然后恢复原先在线的组件。

页面同时预览正面照与循环视频；只有人工点击“确认并使用动态形象”才会构建口型数据并原子切换。生成失败、取消或关页均保留原人物。首次冷生成通常需数分钟，期间实时对话不可用，这是24GiB显存的资源互斥设计。

## 5. 启动与故障恢复

- 双击`Start-cyberWife.cmd`，等四组件功能探针通过后浏览器打开本机页面。
- 状态：`RuntimeLauncher.ps1 -Action status`。
- 单项恢复：`RuntimeLauncher.ps1 -Action recover -Component avatar -Force`（组件可替换为llama/speech/gateway）。
- 双击`Stop-cyberWife.cmd`；重复停止安全。

启动器只管理带PID记录且命令行标记匹配的进程；外部端口占用会失败，不会被强杀。首次全栈启动在ready前回收一次WSL干净页缓存，并等待双侧余量稳定后才进入正式验收。

## 6. 备份、恢复、卸载与永久清除

先停止服务，再查看精确参数：

```bash
python3 ops/data_lifecycle.py backup --help
python3 ops/data_lifecycle.py restore --help
python3 ops/data_lifecycle.py uninstall --help
python3 ops/data_lifecycle.py clear-data --help
```

备份/恢复使用显式源与目标，禁止以`~`、`$HOME`、磁盘根或空变量作为递归目标。`uninstall`默认保留私有数据；`clear-data`是不可恢复动作，必须使用工具要求的二次确认，不由安装器自动调用。

## 7. 验收边界

当前目标机`verify`13/13、真实start/status/Avatar recover/stop×2均通过。真正的“干净机安装PASS”还必须在新的Windows用户或干净VM+WSL执行本页全流程；当前机器的成功不能替代该证据。

在四组件健康、用户已知悉Chrome/Narrator将抢占焦点时，从Windows PowerShell执行现场门：

```powershell
.\ops\acceptance\Invoke-ACC1HumanGate.ps1 -AcceptFocusChange -Operator "验收人姓名"
```

缺少焦点授权时必须在打开窗口前失败。现场报告绑定当前干净Git revision，不保存音频、字幕或回答正文。

现场门与独立干净机门均完成后，在生成干净机报告的Windows用户中执行：

```powershell
.\ops\acceptance\Invoke-V1CompletionAudit.ps1
```

该只读总门要求发布冻结、现场报告和干净机报告属于同一Git revision，并逐文件复算受管源码、依赖、前端和证据SHA。退出0才代表个人/研究用途V1全绿；退出2表示外部报告仍缺失，退出1表示报告失败、过期或与当前代码不一致。
