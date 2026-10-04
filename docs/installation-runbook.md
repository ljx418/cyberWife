# cyberWife V1 安装、验证与数据运维

## 1. 支持范围

Windows 11 + WSL2、NVIDIA RTX 4090级24GiB显卡、宿主32GiB内存。V1不使用Docker。仓库不分发模型、授权照片或声音；准备阶段只接受本机已有的合法工件，不执行静默联网下载。

## 2. 工件位置

- 仓库：默认`C:\workSpace\cyberWife`，可通过参数覆盖。
- llama.cpp：`C:\tools\llama.cpp\llama-server.exe`。
- Qwen3-14B GGUF、Wav2Lip和ComfyUI模型：位置由安装入口参数及模型注册表声明。
- WSL私有根：运行时从当前WSL用户`$HOME/.cyberWife`派生，不固定用户名。
- Cosy/Avatar隔离venv：`$HOME/.cyberWife/venvs/{cosyvoice,avatar-v1-py312}`。

## 3. 三步安装入口

在Windows PowerShell执行：

```powershell
cd C:\workSpace\cyberWife
.\ops\windows\Install-CyberWife.ps1 -Action audit
.\ops\windows\Install-CyberWife.ps1 -Action prepare
.\ops\windows\Install-CyberWife.ps1 -Action verify
```

`audit`只读并逐项报告缺失项；`prepare`只创建缺失的私有目录和runtime配置，已有配置绝不覆盖，可先加`-WhatIf`演练；`verify`要求Windows/WSL/GPU、四组件工件、两个venv、前端构建和模型注册表全部存在，否则退出码2。

安装器不会安装驱动、修改防火墙、下载模型或结束进程。缺少项必须由操作者按来源/许可证准备后重新verify。

## 4. 启动与故障恢复

- 双击`Start-cyberWife.cmd`，等四组件功能探针通过后浏览器打开本机页面。
- 状态：`RuntimeLauncher.ps1 -Action status`。
- 单项恢复：`RuntimeLauncher.ps1 -Action recover -Component avatar -Force`（组件可替换为llama/speech/gateway）。
- 双击`Stop-cyberWife.cmd`；重复停止安全。

启动器只管理带PID记录且命令行标记匹配的进程；外部端口占用会失败，不会被强杀。首次全栈启动在ready前回收一次WSL干净页缓存，并等待双侧余量稳定后才进入正式验收。

## 5. 备份、恢复、卸载与永久清除

先停止服务，再查看精确参数：

```bash
python3 ops/data_lifecycle.py backup --help
python3 ops/data_lifecycle.py restore --help
python3 ops/data_lifecycle.py uninstall --help
python3 ops/data_lifecycle.py clear-data --help
```

备份/恢复使用显式源与目标，禁止以`~`、`$HOME`、磁盘根或空变量作为递归目标。`uninstall`默认保留私有数据；`clear-data`是不可恢复动作，必须使用工具要求的二次确认，不由安装器自动调用。

## 6. 验收边界

当前目标机`verify`13/13、真实start/status/Avatar recover/stop×2均通过。真正的“干净机安装PASS”还必须在新的Windows用户或干净VM+WSL执行本页全流程；当前机器的成功不能替代该证据。
