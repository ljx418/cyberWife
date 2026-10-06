# INST1-AC07 阶段结果

**日期**：2026-10-06  
**结论**：PASS（V1最低部署保证）

已完成：

- ADR-012、计划、逐场景验收、开发前风险闭环、实施审计、PRD检视和外部视角审查；
- `Invoke-INST1SingleMachinePortability.ps1`一键入口；
- `build_single_machine_portability_report.py`证据构建器；
- 最终聚合器双策略及保证等级输出；
- 八项总门合同测试全部通过；Draw.io XML有效。

真实验收结果：

- `.git`写入、Windows PowerShell互操作和loopback绑定均已实测可用；环境变量中的旧`WSL_INTEROP`路径失效，但`powershell.exe`功能调用正常，因此以功能探针为准；
- 261文件离线wheelhouse全量SHA、便携模型工件、受Git跟踪前端、参数化运行路径和替代数据根复核PASS；
- `start×2 → status → recover-avatar → stop×2`全部PASS，恢复时Avatar PID真实变化，最终7860/8010/8011/8090/8091端口关闭且PID记录归零；
- 机器报告写入`%LOCALAPPDATA%\cyberWife\acceptance\INST1-AC07.json`，绑定当前Git revision和release id，`offline_only=true`、12/12步骤PASS；
- 验收脚本实跑发现并修复嵌套PowerShell输出管道等待与PowerShell 5反斜杠路径传递问题，均有合同测试防回归。

复验命令：

```powershell
.\ops\acceptance\Invoke-INST1SingleMachinePortability.ps1 -AcceptReducedAssurance
.\ops\acceptance\Invoke-V1CompletionAudit.ps1
```

本结论只证明报告列出的“同机隔离可移植性”，不声称独立机器、不同Windows身份、不同WSL machine-id或不同GPU驱动兼容。AC06仍可在未来提升保证，但不阻塞私人/研究用途V1。
