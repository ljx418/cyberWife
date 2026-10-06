# INST1 阶段结果

**日期**：2026-10-05
**结论**：CONDITIONAL；INST1.1～INST1.3、隔离Python运行时、离线wheelhouse和当前机真实生命周期已有PASS证据。ADR-012批准AC07作为V1最低部署门，门禁已实现，尚待宿主互操作恢复后生成绑定最终revision的正式报告；AC06干净Windows/WSL降为增强项。

## 已完成

- Gateway默认私有根改为`Path.home()/.cyberWife`；Cosy源码目录支持环境/运行配置。
- RuntimeLauncher动态解析WSL `$HOME`，派生DataRoot、Cosy/Avatar Python、NVIDIA库与Avatar数据目录；显式参数仍可覆盖。
- `Install-CyberWife.ps1`提供audit/prepare/verify与WhatIf安全边界；默认不联网，离线wheelhouse或显式`online + AllowNetworkInstall`才安装两个隔离venv；不下载模型、不修改防火墙、不终止进程。
- 目标机verify 17/17，包含Core/Avatar真实import、动态形象两份工作流及10个ComfyUI必需本地工件；脚本AST解析PASS。
- Speech启动从系统`python3`改为受控Core/Cosy venv；真实VAD/ASR/Embedding预热后healthy，Windows命令行已核对，随后受管停止且端口归零。
- 首轮完整回归发现Speech的HTTP 200仍携带`status=loading`；已拒绝该假阳性并修正为JSON语义健康门。修复后五个端点状态为LLM=`ok`、Speech/Avatar/Avatar-control/Gateway=`ready`，再执行四组件受管停止全部归零。
- 从WSL反向调用Windows启动器时，Windows PowerShell已退出但WSL `/init`会等待长期子进程；自动化只在功能ready后回收该relay。用户双击Windows `.cmd`不经该relay，未把测试工具现象误修成产品逻辑。
- 新入口真实启动四组件全部healthy；Avatar PID `11432→15428`且其他组件保持；stop×2与端口/PID归零PASS。
- 后端全量`344 passed, 5 skipped`；根工具/工作流`15 passed`；前端构建与Headless Playwright `14 passed`。一次错用不存在的`npm test`脚本和两次合并pytest包名冲突均按正确入口重跑通过，未伪装首跑成功。
- 发布冻结器已同步为7个实时模型+10个离线形象模型，并将在线隔离安装与离线wheelhouse结果列为必需证据；同一源码状态连续两次生成的release id与字节完全一致。
- 安装/启动/备份/恢复/卸载/永久清除手册已落盘。
- INST1.2在`/tmp`私有根从零创建Core与Avatar两个Python 3.12环境，均明确`include-system-site-packages = false`；实际在线安装完成，两个`pip check`均为零冲突。首次解析真实暴露`diffusers 0.40`与Cosy所需Transformers/Hugging Face Hub约束冲突，已固定为`diffusers 0.29.0 + huggingface-hub 0.36.2`后重跑通过。
- 当前Ubuntu缺失`python3.12-venv/ensurepip`，安装器真实走通`uv --seed --python /usr/bin/python3`回退；不需要也不会自动执行`sudo apt`。机器可读证据为`audit/v1/INST1/isolated-runtime-result.json`，覆盖Python版本、venv隔离、依赖一致性、核心三方模块以及Gateway/Speech/CosyVoice/LiveTalking/Wav2Lip项目源码导入。
- INST1.3生成Core/Avatar分仓离线wheelhouse：261个wheel、73个同盘硬链接去重、实际7.5GB，清单SHA256全量复算PASS。两个新的Python 3.12 venv只通过`--no-index --find-links`安装，安装器`ready=true`、两套`pip check`无冲突、运行时/项目源码检查10/10 PASS；不传联网授权的构建负例在写目录前返回1。脱敏汇总证据为`audit/v1/INST1/offline-install-result.json`。
- INST1-AC06R独立执行器：分别拒绝开发机Windows SID哈希和WSL machine-id哈希，要求数据根/venv/config/本机注册表执行前均不存在；只允许离线wheelhouse和显式许可/同意的本地制品清单，并自动执行prepare、verify、start×2、status、Avatar recover、stop×2。初版暴露的开发机绝对路径、私有音频硬编码和缺省Avatar缺失均已修复；当前机私有迁移、真实四组件启动/Avatar恢复/双停归零通过。

## 未完成

没有第二个全新Windows 11用户或干净VM+WSL可用，因此项目不声称跨Windows用户、WSL发行版或GPU驱动复现。AC07只在报告中签署同机隔离可移植性；未来仍可用AC06提升保证，无需迁移产品架构。

开放P1：`INST1-P1-01 干净Windows+WSL独立复现待执行`。AC06R工具已就绪，但没有新环境PASS报告前不得签INST1或V1全绿。
