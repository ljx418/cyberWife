# B4 自动化实施、验收与审计计划

**状态**：APPROVED FOR IMPLEMENTATION（2026-09-26）  
**入口门**：B3 AC01～AC07、B2/B2.5回归与PRD检视均PASS；B3真实来源会话固定使用 `session_id=470`。  
**范围**：FR-02、FR-11～14、NFR-04/05/06/07/09；不提前实现B5发布组合能力。

## 共同硬门

- 所有正式E2E使用本机SQLite、真实sqlite-vec、真实BGE和B3真实会话数据；mock只允许确定性故障注入。
- 每个子阶段先执行合同/集成测试，再执行对应真实验收；失败即回到本文件修订，不跳项。
- MemoryRepository独占事务；任何编辑、删除或全清必须使source/FTS/vector/cache同成同败。
- sqlite-vec缺失、512维不匹配或往返probe失败时fail-closed；禁止以内存或FTS-only冒充ready。
- no-record业务数据增量必须为0；原始麦克风音频任何策略均不得落盘。
- 项目RAM≤14GB、VRAM≤22GB，且Windows/WSL各保留≥2GB；不得新增常驻模型。

## 顺序、开发内容与子阶段验收

| 子阶段 | 实施实体 | 验收与出门门槛 | 开发前审计 |
|---|---|---|---|
| B4.0 基线锁定 | `VectorIndex`、现有repository/migration合同 | 测试准确暴露内存fallback和内部commit；保存改造前结果 | 只增加测试与证据；不得先删旧路径，P0/P1=0 |
| B4.1 事务与索引 | `MemoryRepository`、无commit `VectorIndex`、BGE/health probe、migration | sqlite-vec/BGE真实往返；故障逐写回滚；维度/扩展错误非ready | 事务所有权唯一；连接锁与WAL边界明确，P0/P1=0 |
| B4.2 形成与召回 | `MemoryService`、候选抽取、去重、FTS+vector融合、`PromptCompiler`预算 | B3 session 470派生稳定/临时事实；稳定可追踪召回，低置信不固化；≤4条/≤800 token | 不让候选或技术细节进入回答；生成/取消围栏覆盖异步任务，P0/P1=0 |
| B4.3 管理与彻删 | memory REST、编辑/单删/全清、脱敏审计 | AC03～05：旧值0、新值可命中；四层0召回；全清确认、回滚、重试幂等 | 禁止UI先删；审计无敏感正文；全清须412确认，P0/P1=0 |
| B4.4 不记录 | 创建态none内存session；中途单向切换、取消与补偿删除 | AC06/07：5轮、重启、WAL/日志/文件/loopback扫描；整场五类业务表和向量增量0 | ID不得进入envelope/log/audit/error；切换后不可恢复记录，P0/P1=0 |
| B4.5 保留/磁盘 | `RetentionService`、注入时钟、启动扫描、03:00调度、重试、低盘保护 | AC08/09：29/30/31天边界；只删>30天会话文本/摘要；长期记忆保留；低盘无误删 | 固定表白名单；失败整批回滚；不自动删资产/DB/备份/长期记忆，P0/P1=0 |
| B4.6 阶段总验收 | B4全部runner、全量回归、PRD检视 | AC01～09全部PASS；B3打断、B2.5首响、B2 Avatar烟测无回退 | 独立检查证据来源、失败样本和门槛，开放P0/P1=0才进入B5 |

## 当前开发前审计（B4.0）

| 检查项 | 结果 | 处置 |
|---|---|---|
| B3真实入口证据 | PASS | 使用 `audit/v1/B3/AC05/manifest.json` 的 session 470 |
| 当前fallback/commit行为可观察 | PASS | 先以合同测试和基线报告锁定，不以现状形成产品PASS |
| 数据破坏风险 | CLOSED | B4.0仅使用临时数据库，不触碰真实用户库 |
| 规格/架构冲突 | PASS | 与PRD、`plan.md`、implementation contracts一致 |
| 开放P0/P1 | 0 | 允许进入B4.0；后续子阶段需在 `execution-log.md` 逐项重审 |

