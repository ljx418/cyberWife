# ACC1 阶段结果

**日期**：2026-10-05
**结论**：CONDITIONAL；自动化部分PASS，人工Narrator播报听感和物理麦克风门未执行，不得标记AC-11全绿。

## 已通过

- 新增三视口完整键盘旅程：1920×1080、1366×768、420×720各完成设置、开聊、打断、改人设、删隔离记忆，共15/15任务。
- 每个视口验证无横向溢出、axe serious/critical=0、对话状态由WS事件合同驱动。
- 前端构建PASS；Playwright全量14/14 PASS（原11项+3项完整旅程）。
- 首轮测试发现删除`alertdialog`被外层设置Dialog抢走Tab圈闭；已修为确认框优先圈闭、自动聚焦，关闭后恢复原触发点或安全回退点。

## 真实设备检查

- Windows检测到真实录音端点，包括`Microphone (Shure MV7)`、AB13X USB Audio、GENERAL WEBCAM与Realtek麦克风。
- Windows Narrator与Chrome已检出；NVDA未安装不再被错记为唯一阻断。ACC1-AC05仍需人类对实际播报可理解性签字。
- 未启动有界面Chrome，未抢用户焦点，未采集物理麦克风；ACC1-AC06保持未验收。
- 已新增`ops/acceptance/Invoke-ACC1HumanGate.ps1`；脚本必须显式给出`-AcceptFocusChange`，引导Narrator五任务与实体麦克风3轮+1次打断，只保存布尔签字而不保存对话或原始音频。

在四组件已健康且操作者准备好让Chrome/Narrator抢占焦点时，从Windows PowerShell执行：

```powershell
.\ops\acceptance\Invoke-ACC1HumanGate.ps1 -AcceptFocusChange -Operator "验收人姓名"
```

脚本只关闭自己启动的隔离Chrome和Narrator（若Narrator原本在运行则保留），证据输出到`audit/v1/ACC1/human-gate.json`。

## 证据边界

三视口旅程运行生产React组件与真实REST/WS字段合同，但后端响应和媒体设备为隔离替身，避免触碰正式记忆；它只签AC01～04的前端自动化部分，不能替代正式Gateway模型链、NVDA或物理输入。真实模型链由RES1独立证明，但两类证据不可相互拼接冒充端到端物理麦克风旅程。

开放P1：`ACC1-P1-01 Narrator真实播报待人工签字`、`ACC1-P1-02 物理麦克风Chrome自由对话待现场执行`。本阶段不能签PASS。
