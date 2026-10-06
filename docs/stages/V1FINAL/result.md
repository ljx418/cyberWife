# V1FINAL 阶段结果

**日期**：2026-10-06
**结论**：AUTOMATION COMPLETE / HUMAN TOTAL ACCEPTANCE PENDING

## 已完成

- 新增headed Chrome人机绑定取证器及独立核心模块。
- PowerShell入口保留显式焦点授权、运行健康预检、Narrator安全生命周期和非零失败退出码。
- 三轮、打断、取消后接续、PCM活动轨道、当前人物、live Canvas、Idle恢复和健康前后均由机器判断。
- 人工仅判断Narrator五任务、口型同步、嘴部自然、Idle自然及停止后体验；自然度低于4/5直接失败。
- 报告只记录路由元数据、计数和布尔/评分，不保存原始音频、字幕或回答正文。
- Windows Node与WSL Node核心单测均3/3通过；AC06R后安装合同11/11、制品准备器3/3、焦点保护、Node语法和PowerShell AST通过。
- 当前全量不抢焦点回归：后端361 passed/7 skipped；根37 passed；Avatar13 passed；前端build、Playwright16 passed；取证核心3/3。
- UX8真实四进程授权PCM 3/3通过，普通话词形归一与900ms句中停顿机器门通过；物理麦克风主观复验并入本阶段现场门，不由fixture代签。
- AC09最终总门按显式策略接收AC07单机隔离报告或AC06独立机报告；两个schema不可互换，报告公开保证等级。现场报告仍绑定Git revision，总门重新核验细项而非只信顶层PASS。
- AC07最低部署门已在当前宿主从零重跑：12/12步骤PASS，双启动、Avatar恢复、双停止和端口/PID归零均成立；AC09复核部署分门PASS。
- PRD、架构、计划、验收、追踪矩阵、命令清单、全局状态和8页Draw.io已同步当前事实。

## 尚未执行

本轮按约定没有擅自打开Chrome/Narrator或采集物理麦克风，因此只剩现场结构化人工总验收。执行前需明确通知用户电脑焦点将被占用。全新Windows用户+干净WSL的AC06保留为增强项，AC07不会冒充它。

## 现场命令

```powershell
.\ops\acceptance\Invoke-ACC1HumanGate.ps1 -AcceptFocusChange -Operator "验收人姓名"
```

只有`audit/v1/ACC1/human-gate.json`总结果为`PASS`且命令退出码为0，才可关闭ACC1与UX6现场门。
