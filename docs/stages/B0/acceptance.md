# B0 验收标准

1. `start/status/recover/stop` 连续三轮幂等；重复 start 不产生第二实例。
2. 端口被非项目进程占用时 fail closed，绝不终止该进程。
3. Gateway 使用有效 CLI/config 启动；llama 使用 `/health`；六组件状态均来自实时 probe。
4. 损坏模型、不可达服务、sqlite-vec 往返失败不得显示 ready。
5. 资源响应包含非空 RAM/磁盘；GPU 可用时包含 device 总量和项目进程数据。
6. 真实 Qwen/ASR/LLM/Avatar/Embedding/VAD 功能探针保存模型 ID、哈希、设备和结果；mock 不计。
7. 宿主31.82GB、启动前约16GB可用；接受当前WSL 15.52GiB上限。项目private bytes+RSS≤14GB且宿主/WSL均保留约2GB；以进程数据、`Available MBytes`、`/proc/meminfo`和swap-in佐证。
8. 基础回归全绿，且真实模型跳过项必须单独列为未验收，不能忽略。

## 2026-09-24 执行结果

| 条目 | 结果 | 证据 |
|---|---|---|
| 1 三轮生命周期与幂等 | PASS | `audit/v1/B0/lifecycle-e2e.md` |
| 2 外来端口 fail closed | PASS | 受控 8091 占用测试，外来进程存活、本轮进程回滚 |
| 3 有效配置与实时状态 | PASS | 四服务启动及 Gateway 六组件组合 probe |
| 4 失败不得 ready | PASS | Avatar 不在线时 503；probe-only 状态机与回归测试 |
| 5 真实资源响应 | PASS | RAM/磁盘/VRAM 非空实测值 |
| 6 六组件真实功能探针 | PASS | `audit/v1/B0/*-runtime-probe.md` 与组合证据 |
| 7 约16GB可用预算 | PASS | 用户批准新预算；组合探针采样WSL总用量8.86/15.52GB，无OOM；B2/B3继续采集项目可归因峰值 |
| 8 回归与跳过解释 | PASS | 233 passed / 4 skipped；真实 PowerShell E2E 已覆盖 skip 项 |

阶段总判定：**PASS**。用户已批准 V1.3 内存预算纠正，B0全部出门条件关闭，可以进入B1。
