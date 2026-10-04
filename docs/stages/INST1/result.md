# INST1 阶段结果

**日期**：2026-10-05
**结论**：CONDITIONAL；INST1.1修正后实现与目标机验证PASS，干净Windows/WSL外部环境复现未执行。

## 已完成

- Gateway默认私有根改为`Path.home()/.cyberWife`；Cosy源码目录支持环境/运行配置。
- RuntimeLauncher动态解析WSL `$HOME`，派生DataRoot、Cosy/Avatar Python、NVIDIA库与Avatar数据目录；显式参数仍可覆盖。
- `Install-CyberWife.ps1`提供audit/prepare/verify与WhatIf安全边界；默认不联网，离线wheelhouse或显式`online + AllowNetworkInstall`才安装两个隔离venv；不下载模型、不修改防火墙、不终止进程。
- 目标机verify 17/17，包含Core/Avatar真实import、动态形象两份工作流及10个ComfyUI必需本地工件；脚本AST解析PASS。
- Speech启动从系统`python3`改为受控Core/Cosy venv；真实VAD/ASR/Embedding预热后healthy，Windows命令行已核对，随后受管停止且端口归零。
- 首轮完整回归发现Speech的HTTP 200仍携带`status=loading`；已拒绝该假阳性并修正为JSON语义健康门。修复后五个端点状态为LLM=`ok`、Speech/Avatar/Avatar-control/Gateway=`ready`，再执行四组件受管停止全部归零。
- 从WSL反向调用Windows启动器时，Windows PowerShell已退出但WSL `/init`会等待长期子进程；自动化只在功能ready后回收该relay。用户双击Windows `.cmd`不经该relay，未把测试工具现象误修成产品逻辑。
- 新入口真实启动四组件全部healthy；Avatar PID `11432→15428`且其他组件保持；stop×2与端口/PID归零PASS。
- 后端全量`344 passed, 5 skipped`；根工具/工作流`12 passed`；前端构建与Headless Playwright `14 passed`。一次错用不存在的`npm test`脚本和两次合并pytest包名冲突均按正确入口重跑通过，未伪装首跑成功。
- 发布冻结器已同步为7个实时模型+10个离线形象模型，同一源码状态连续两次生成的release id与字节完全一致。
- 安装/启动/备份/恢复/卸载/永久清除手册已落盘。

## 未完成

没有第二个全新Windows 11用户或干净VM+WSL可用，因此INST1-AC06未执行。目标机verify证明工件完整和参数迁移有效，但不能证明从零安装的依赖准备步骤在另一环境无遗漏。

开放P1：`INST1-P1-01 干净Windows+WSL独立复现待执行`。不得签INST1或V1全绿。
