# V1RC1-AC05-R2 修复计划：延迟与RAM双门

**触发证据**：修复后的1分钟工具smoke完成当前Crop V2协议v2、1完整+1打断，但项目RAM峰值15332.25MiB，超过14GiB；WSL最低可用仍7403MiB，说明仅用系统余量触发trim不足以约束项目预算。

## 修正

- 保留 R3 每轮首包窗口复位。
- `release_transient_memory` 在任一条件成立时trim：WSL `MemAvailable`<3072MiB，或Gateway当前RSS>4096MiB，或指标不可读。
- 指标记录trim原因与当前RSS；不改变模型、音色、整句合成或音频参数。

## 重新验收

1. 单测覆盖系统压力、进程RSS压力、健康状态和fail-safe。
2. 同语料Windows Chrome 30轮P95≤7秒，确认trim没有抵消R3。
3. 1分钟2动作资源smoke：项目RAM≤14GiB且当前人物/协议/动作完整；趋势门预期因时长不足而FAIL。
4. 两项同时满足后才从零进入60分钟。
