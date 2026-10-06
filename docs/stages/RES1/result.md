# RES1 验收结果

**日期**：2026-10-05
**结论**：PASS；AC-14 Windows宿主内存余量阻断已由同一提交、同一目标机的完整60分钟复验关闭。

## 真实组合证据

证据目录：`audit/v1/RES1/AC14-rerun-20261005/`

| 指标 | 实测 | 门槛 | 结果 |
|---|---:|---:|---|
| 完整轮 | 20/20 | 20 | PASS |
| 打断轮 | 10/10 | 10 | PASS |
| 项目RAM峰值 | 13,558.773MiB | ≤14,336MiB | PASS |
| GPU显存峰值 | 10.497GiB | ≤22GiB | PASS |
| Windows最低可用 | 4,124.074MiB | ≥2,048MiB | PASS |
| WSL最低可用 | 9,162.562MiB | ≥2,048MiB | PASS |
| 后30分钟RAM斜率 | 0.5797MiB/min | ≤20MiB/min | PASS |
| task/runtime/queue/thread斜率 | 全部0 | ≤0.1/min | PASS |
| 首响P95斜率 | -1.956733ms/min | ≤20ms/min | PASS |
| 连续重大swap分钟 | 0 | <3 | PASS |

## 生命周期

- 重复`start`保持同一PID记录。
- Avatar强制恢复：Windows记录PID `12432 → 22088`；LLM、Speech、Gateway PID不变。
- `stop`连续执行两次均成功；受管端口为空、PID记录数为0。
- `lifecycle.json.pass=true`，soak退出码0。

## 诚实边界

冷启动模型装载期间Windows可用内存曾瞬时降至438.738MiB；一次性WSL干净页缓存回收后，在36.75秒内形成连续三次Windows/WSL均≥3GiB的启动准入，正式60分钟采样才开始。该瞬时不属于“可接收用户会话”的运行窗口，但仍说明32GiB是当前推荐下限，不能把启动器的ready前等待移除，也不能宣称低于32GiB硬件已验证。

开放Critical/Major规格偏差=0；RES1关闭资源红项，AC07已关闭V1最低部署证据，V1总发布现只受AC-11/物理麦克风与主观现场报告约束。
