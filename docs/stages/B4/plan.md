# B4 详细开发计划：记忆、隐私与保留

**状态**：PLANNED；尚未进入产品代码开发  
**前置门**：B3 `e2e_accepted`，且 B4 文档审计 P0/P1=0  
**目标体验**：角色能恰当地记住稳定事实；用户能看见来源、纠正和彻底删除记忆；“本次不记录”确实不留下业务数据。

## 1. 固定数据设计

- Embedding 固定 `bge-small-zh-v1.5`、512维；sqlite-vec 未加载、维度不符或 insert/search/delete 往返失败时启动阻断，禁止以内存或 FTS-only 冒充 ready。
- 检索：FTS5 top-6 + vector top-4；向量 cosine≥0.55；融合后最多4条、总计≤800 token进入 PromptCompiler。
- 会话结束后异步抽取稳定事实；置信度≥0.80才固化，0.60～0.79只作为进程内待确认候选，低于0.60丢弃。候选不进入检索和回答。
- 去重以标准化文本、来源和向量相似度共同判断；编辑后的用户值优先于自动候选。

**现状改造门**：当前 `VectorIndex` 的内存 fallback 与内部提交路径必须先被合同测试捕获，再拆为由 `MemoryRepository` 注入 connection/cursor 的无提交索引操作；sqlite-vec 扩展关闭时 health 必须为 error/degraded，现有 FTS 查询可以用于诊断但不能形成 ready。改造前后分别归档回归结果，禁止直接删除旧路径后声称完成。

## 2. 原子事务

MemoryRepository 持有唯一 SQLite 事务边界。单条 upsert/edit/delete 和 purge-all 同时维护 `memories`、`memory_fts`、`memory_vectors`/meta、派生缓存和脱敏审计；VectorIndex 不得内部 commit。故障任一点回滚全部修改。

全清接口为 `DELETE /api/v1/memories`，请求体必须含 `{"confirmation":"PURGE_ALL"}`，缺失或错误返回 `memory.confirm_required`/412。

## 3. no-record 合同

- 创建即不记录：Orchestrator 从 `2**62` 起分配进程内十进制 session ID，不插入 `sessions`。该 ID 只存在于 Orchestrator 进程内作用域，不进入 WS/REST envelope、日志、审计或错误响应。
- 会话中开启：先提升 generation、取消待写任务，再在单事务中删除该 session 的 turn/transcript/summary、候选和由其产生的 memory/vector，随后继续使用同一个内存 ID。
- 一旦开启，本 session 不允许恢复记录；原始麦克风音频任何模式均不落盘。
- 无正文的 `session.no_record` 审计事件允许保留，不计入 AC-09 业务数据增量。

## 4. 保留与隐私

- 过期条件为 `expires_at < now`；恰好30天不删，超过30天才删。
- 只清理 sessions/turns/transcripts/summaries，不删除长期记忆、授权、人物、人设和资产版本。
- 启动扫描一次，每日本地03:00运行；失败整批回滚，60秒起指数重试最多6次。
- `RETENTION_NOW` 仅测试/验收启用；非法值返回 `retention.invalid_clock`。
- `~/.cyberWife` 所在文件系统可用空间<10GiB时，阻止模型下载、模型/KV/预热、ASR解码、Avatar帧、派生索引重建和验收媒体等可重建缓存；已打开的业务事务与脱敏安全审计继续，日志先轮转再限流。不能自动删除用户资产、数据库、备份或长期记忆。

## 5. 开发子阶段

1. B4.0 以故障测试锁定现有 fallback/commit 行为，建立改造前证据。
2. B4.1 repository事务、sqlite-vec fail-closed和 BGE functional probe。
3. B4.2 MemoryService、候选提取、融合检索、prompt预算和来源展示。
4. B4.3 编辑、单删、全清、回滚和审计。
5. B4.4 no-record创建/会话中切换/重启不可恢复。
6. B4.5 RetentionService、可注入时钟、启动补偿、重试和低磁盘。
7. B4.6 按 [`../../acceptance-command-manifest.md`](../../acceptance-command-manifest.md) §3 使用真实 B3 会话 E2E、隐私扫描和 PRD 检视。

每个子阶段均执行计划→开发前审计→合同/集成→真实E2E→PRD检视；失败返回计划阶段。
