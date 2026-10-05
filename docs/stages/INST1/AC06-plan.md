# INST1-AC06 干净环境独立复现执行计划

> 历史计划：实现后发现制品可移植性缺口，已由`AC06R-plan.md`取代，不得单独作为正式执行依据。

**日期**：2026-10-06
**状态**：开发中

## 目标

提供一个只能在全新Windows用户与干净默认WSL发行版上通过的总验收入口。入口先输出当前环境指纹；正式执行必须显式拒绝开发机的Windows SID哈希和WSL machine-id哈希，并证明应用数据根、运行时venv和本机配置在执行前不存在。随后仅使用本地项目、离线wheelhouse、CosyVoice源码和模型工件完成准备、验证与完整生命周期。

## 实施顺序

1. `fingerprint`只读输出Windows用户SID哈希、WSL machine-id哈希、OS/WSL版本和干净前置状态。
2. `accept`要求显式`-AcceptCleanEnvironment`及两个开发机拒绝哈希；任一身份相同立即失败。
3. 前置检查数据根、两个venv与`runtime.local.toml`均不存在，避免既有状态污染。
4. 调用现有安装器，以分组件离线wheelhouse准备隔离Python 3.12运行时；复制明确给出的本地CosyVoice源码工件，不联网下载模型。
5. 执行安装器`verify`，随后执行RuntimeLauncher `start×2 → status → recover avatar → stop×2`。
6. 报告只保存哈希、布尔门、组件健康和退出码，不保存用户名、SID原文、machine-id、模型绝对路径或日志正文。
7. 任何失败均在finally执行受管stop；不得结束未被启动器记录的外部进程。

## 非目标

- 不创建Windows用户、不安装/注册/注销WSL、不安装GPU驱动。
- 不联网下载模型、依赖或源码。
- 不把当前WSL导出后重新导入冒充新发行版。
- 本工具在当前开发机上的单元/合同通过不能关闭AC06；必须取得新环境正式报告。
