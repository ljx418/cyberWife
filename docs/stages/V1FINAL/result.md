# V1FINAL 阶段结果

**日期**：2026-10-07
**结论**：PASS — AUTOMATION + PROJECT OWNER HUMAN ACCEPTANCE + AC07 + FINAL AGGREGATION

## 已完成

- 新增headed Chrome人机绑定取证器及独立核心模块。
- PowerShell入口保留显式焦点授权、运行健康预检、Narrator安全生命周期和非零失败退出码。
- 三轮、打断、取消后接续、PCM活动轨道、当前人物、live Canvas、Idle恢复和健康前后均由机器判断。
- 人工判断Narrator五任务、嘴型是否实际变化、开始/结束切换连续性及停止后体验；`mouth_motion_observed`不为真，或出现黑帧、冻结、遮罩、双人物、切换闪动均直接失败。口型同步、嘴部自然度与清晰度继续如实评分，但按项目所有者2026-10-07决议作为V2-X基线，不再单独阻断V1。
- 报告只记录路由元数据、计数和布尔/评分，不保存原始音频、字幕或回答正文。
- Windows Node与WSL Node核心单测当前均4/4通过；AC06R后安装合同11/11、制品准备器3/3、焦点保护、Node语法和PowerShell AST通过。
- 2026-10-07当前全量不抢焦点回归：后端375 passed/7 skipped；根58 passed；Avatar16 passed；前端build、Playwright24 passed；取证核心4/4。
- UX8真实四进程授权PCM 3/3通过，普通话词形归一与900ms句中停顿机器门通过；物理麦克风主观复验并入本阶段现场门，不由fixture代签。
- AC09最终总门按显式策略接收AC07单机隔离报告或AC06独立机报告；两个schema不可互换，报告公开保证等级。现场报告仍绑定Git revision，总门重新核验细项而非只信顶层PASS。
- AC07最低部署门已在当前宿主从零重跑：12/12步骤PASS，双启动、Avatar恢复、双停止和端口/PID归零均成立；AC09复核部署分门PASS。
- PRD、架构、计划、验收、追踪矩阵、命令清单、全局状态和8页Draw.io已同步当前事实。
- 修复Avatar实时PCM 20ms到包与10ms出队超时不匹配导致的伪静音插入；当前active avatar四段真实CosyVoice样本嘴部响应比1.132～1.279，黑帧/冻结/传输丢帧均为0，机器嘴部响应门4/4通过。

## 人工总验收

项目所有者于2026-10-07按最终HTML报告完成实际交互体验，并明确确认人工验收通过。该结论关闭物理麦克风、听感、真人打断、同一人物口型、连续三次启停与停止后Idle等V1主观门；未提供更细评分的项目只按4/5最低通过边界记录，不推定更高质量。完整记录见[`human-acceptance.md`](human-acceptance.md)。全新Windows用户+干净WSL的AC06仍为增强项，AC07不会冒充它；高清与嘴部自然度提升转入V2-X8。

## 现场命令

```powershell
.\ops\acceptance\Invoke-ACC1HumanGate.ps1 -AcceptFocusChange -Operator "验收人姓名"
```

最终候选已生成同revision的`audit/v1/ACC1/human-gate.json`、发布冻结清单与AC07报告，`audit_v1_completion.py`三门聚合结果为`PASS`，V1正式关闭。
