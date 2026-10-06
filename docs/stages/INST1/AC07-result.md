# INST1-AC07 阶段结果

**日期**：2026-10-06  
**结论**：IMPLEMENTED / REAL HOST RUN PENDING

已完成：

- ADR-012、计划、逐场景验收、开发前风险闭环、实施审计、PRD检视和外部视角审查；
- `Invoke-INST1SingleMachinePortability.ps1`一键入口；
- `build_single_machine_portability_report.py`证据构建器；
- 最终聚合器双策略及保证等级输出；
- 八项总门合同测试全部通过；Draw.io XML有效。

未完成：

- 当前终端的`/run/WSL/..._interop` socket缺失，WSL无法启动Windows PowerShell；
- 当前权限把`.git`设为只读，无法提交后生成绑定最终revision的新release manifest；
- 因而尚未生成绑定最终Git revision的`INST1-AC07.json`，最终总门不得把本阶段写成PASS。

环境恢复后执行：

```powershell
.\ops\acceptance\Invoke-INST1SingleMachinePortability.ps1 -AcceptReducedAssurance
.\ops\acceptance\Invoke-V1CompletionAudit.ps1
```

第一条命令完成前不得声称独立机器兼容；即使通过，也只签署报告内列出的单机隔离保证。
