# INST1 阶段结果

**日期**：2026-10-05
**结论**：CONDITIONAL；实现与目标机验证PASS，干净Windows/WSL外部环境复现未执行。

## 已完成

- Gateway默认私有根改为`Path.home()/.cyberWife`；Cosy源码目录支持环境/运行配置。
- RuntimeLauncher动态解析WSL `$HOME`，派生DataRoot、Cosy/Avatar Python、NVIDIA库与Avatar数据目录；显式参数仍可覆盖。
- 新增`Install-CyberWife.ps1`的audit/prepare/verify与WhatIf安全边界；无下载、无防火墙修改、无进程终止。
- 目标机verify 13/13；脚本AST解析PASS。
- 新入口真实启动四组件全部healthy；Avatar PID `11432→15428`且其他组件保持；stop×2与端口/PID归零PASS。
- 后端全量`343 passed, 5 skipped`。
- 安装/启动/备份/恢复/卸载/永久清除手册已落盘。

## 未完成

没有第二个全新Windows 11用户或干净VM+WSL可用，因此INST1-AC06未执行。目标机verify证明工件完整和参数迁移有效，但不能证明从零安装的依赖准备步骤在另一环境无遗漏。

开放P1：`INST1-P1-01 干净Windows+WSL独立复现待执行`。不得签INST1或V1全绿。
