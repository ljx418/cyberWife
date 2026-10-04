# B0 审计记录

**日期**：2026-09-24  
**当前结论**：PASS；用户批准按32GB整机、约16GB可用预算开发，原WSL 28GB门禁已撤销，可以进入B1。

## 实施前结论

PASS，可开始 B0 代码开发。

- PRD 对齐：覆盖 FR-03、FR-15、FR-17、FR-18 与 NFR-02/03/04/09/10。
- 架构对齐：保留模块化单体和本机推理进程，不引入 Docker/云端/新视觉范围。
- 防虚假验收：223 PASS / 4 SKIP 仅记 baseline；B0 必须补真实 probe 与生命周期证据。
- 数据安全：不删除现有模型或资产；资产复制到 ext4 时保留源文件。
- 高风险点：`.wslconfig` 修改及 `wsl --shutdown` 必须在 B0 末暂停并由用户确认。
- 未关闭 P0/P1：0。外审项目已在 §35 和本阶段验收标准中闭环。
- 二次 Claude Code 只读复审结论：PASS，允许 DEV-B0；§34/§35 已取代 §15/§24/§30 的历史启动结论。

## 实施中审计意见 B0-P1-01

- 发现：组合探针首次运行时，TTS 超过 Gateway 300秒超时，而 SpeechRuntime 子进程继续运行。
- 原因：SpeechRuntime 子进程 timeout=600秒，大于 Gateway HTTP timeout=300秒；最小探针文本还生成了13.6秒音频。
- 关闭：探针改为2字、最长5秒；SpeechRuntime 子进程硬超时改为120秒，低于 Gateway 300秒；失败子进程已按精确 PID 回收；组合驻留复测 TTS 35,659ms 返回 ready，遗留子进程为零。
- 状态：**CLOSED**。

## 实施中审计意见 B0-P1-02

- 发现：Windows `Get-NetTCPConnection` 未枚举 WSL 监听者，外来 8091 占用会等待健康超时；失败启动的组件还可能留下 stale PID record。
- 关闭：增加 localhost TCP connect 跨边界检测；单组件健康启动失败时仅回收拥有 marker 的本次进程并删除记录。
- 复测：受控外来 8091 进程仍存活，启动器 fail closed、llama 回滚、PID 记录全空。
- 状态：**CLOSED**。

## B0 出门审计

- 自动回归：233 passed / 4 skipped；skip 原因已在真实 PowerShell 生命周期证据中覆盖。
- 三轮生命周期、重复启动/停止、单组件恢复、失败回滚、外来端口保护均通过。
- 六组件在同一组合驻留环境下全部真实 probe ready；未以 mock、文件存在或 checkpoint-only 冒充 ready。
- PRD 规格检视：除目标机 WSL 内存配额外，无新增 P0/P1、无范围漂移。
- `B0-HG-01` 关闭：2026-09-24 用户明确说明目标机32GB物理内存、空闲仅约16GB，并批准按该预算开发。外部攻略的公开规格也是“16G起步，32G更稳”，原“WSL至少28GB”属于错误推导。
- 新门槛：项目可归因峰值≤14GB，约16GB启动预算保留约2GB余量；持续swap-in或WSL `MemAvailable<2GB`失败。B0短时组合采样无OOM，B2/B3继续做峰值与稳态证据。
- 未关闭 P0/P1：0。B0最终状态：**PASS**。
