# INST1 详细开发计划：干净机安装可复现性

**日期**：2026-10-05

## 目标

消除运行入口对`Administrator`用户和既有目录的隐式绑定，提供可审计的安装前检、配置生成和安装后验证，使新Windows用户/干净WSL可按明确的本地工件清单完成部署。

## 实施内容

1. RuntimeLauncher运行时解析WSL `$HOME`，派生数据根、Cosy/Avatar venv、NVIDIA库与Avatar数据目录；所有值仍允许显式覆盖。
2. Gateway默认数据根使用当前Linux用户home；CosyVoice源码目录从环境/运行配置读取。
3. 新增`Install-CyberWife.ps1`：`audit/prepare/verify`三态，检查Windows/WSL/GPU/模型/venv/前端构建，生成不含用户名硬编码的本机runtime配置；不静默下载模型、不修改全局防火墙。
4. 增加PowerShell合同测试和隔离临时目录dry-run；当前目标机执行verify。
5. 输出安装、备份、卸载和数据清除边界文档。

## 停止条件

脚本不得结束外部进程、不得覆盖已有私有配置/数据、不得把模型文件纳入Git。没有第二台干净Windows/WSL时，只能签“安装器合同/目标机verify”，不能冒充干净机端到端PASS。
