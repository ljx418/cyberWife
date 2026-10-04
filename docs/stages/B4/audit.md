# B4 开发前审计与开发后复核

**当前结论**：DEVELOPMENT + ACCEPTANCE PASS；开放P0/P1=0。

| 风险 | 等级 | 关闭方式 | 状态 |
|---|---|---|---|
| none策略仍创建session/空turn | P0 | 创建即none使用内存ID；中途开启做整场补偿删除 | CLOSED + REAL E2E |
| VectorIndex内部commit产生半删 | P0 | repository独占事务，index不commit | CLOSED + FAULT MATRIX |
| sqlite-vec缺失仍显示ready | P1 | 启动往返probe fail-closed | CLOSED + CONTRACT |
| 删除只清UI或源表，仍可语义召回 | P0 | source/FTS/vector/cache四层验收 | CLOSED + REAL BGE |
| 保留任务误删长期记忆 | P0 | 固定扫描表白名单和回滚测试 | CLOSED + 29/30/31 CLOCK |
| B4使用mock会话冒充真实数据 | P1 | 入口要求B3 e2e session ID与证据链 | CLOSED + REAL AUDIO/MODELS |

实际实现没有新增常驻模型：BGE复用Speech Worker；事务由`SqliteMemoryRepository`与`RetentionService`分别持有明确边界。第一次B4.2复合召回失败、第一次B4.4播放确认失败、第一次B4.6类型回归均保留失败证据并完成修复重验，没有覆盖失败历史。B4可进入B5开发前阶段门。
