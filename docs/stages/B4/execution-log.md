# B4 自动化开发与验收审计记录

**执行日期**：2026-09-26  
**当前状态**：PASS；B4关闭，允许进入B5开发前阶段门。

## 阶段记录

| 子阶段 | 开发前审计 | 实施 | 真实/合同验收 | PRD检视 | 状态 |
|---|---|---|---|---|---|
| B4.0 基线锁定 | P0/P1=0 | 已捕获fallback/commit | 基线合同PASS | 不签产品规格 | PASS |
| B4.1 事务与索引 | P0/P1=0 | 已完成 | 10合同+真实BGE/sqlite-vec PASS | FR-12/NFR-05/07无偏移 | PASS |
| B4.2 形成与召回 | P0/P1=0 | 已完成 | 真实音频/模型/索引 PASS | FR-12/NFR-04/07无偏移 | PASS |
| B4.3 管理与彻删 | P0/P1=0 | 已完成 | 23合同+真实编辑/删除/全清 PASS | FR-12/NFR-04/07无偏移 | PASS |
| B4.4 不记录 | P0/P1=0 | 已完成 | 42合同+10轮真实链路 PASS | FR-02/13、NFR-04/06无偏移 | PASS |
| B4.5 保留/磁盘 | P0/P1=0 | 已完成 | 29/30/31天真实SQLite/sqlite-vec PASS | FR-14/NFR-09无偏移 | PASS |
| B4.6 总验收 | P0/P1=0 | 已完成 | 全量回归+真实跨阶段烟测 PASS | B4规格检视PASS | PASS |

任何失败、退回计划、根因、门槛修订和原始证据路径均追加于此，不覆盖历史记录。

## B4.0 结果与B4.1开发前审计

- `audit/v1/B4/B4.0/vector-index-before.json` 证明旧实现会在sqlite-vec不可用时接受内存写入，并在真实sqlite-vec insert/delete各自行一次commit。
- 该结果只证明迁移起点，不构成产品能力；未访问用户数据库，PRD没有提前签署。
- B4.1采用独立 `SqliteMemoryRepository` 持有 `BEGIN IMMEDIATE/COMMIT/ROLLBACK`，`VectorIndex` 只执行cursor操作；BGE适配器固定本地模型、CPU、512维和归一化。
- 故障点覆盖source/FTS/vector/meta/audit；连接锁覆盖完整事务；扩展、维度或往返失败时构造失败并由health报告error。
- 语意、依赖方向、资源预算与B4计划一致；开放P0/P1=0，允许进入B4.1。

## B4.1 结果与B4.2开发前审计

- `audit/v1/B4/B4.1/storage-probe.json`：真实本地BGE 512维、真实sqlite-vec语义命中，vector写后故障四层计数不变；10项事务合同全部通过。
- 生产组合采用Speech Worker共享BGE，不在Gateway重复驻留PyTorch；真实四服务重启成功，embedding endpoint ready。
- B4.2固定规则：稳定事实≥0.80固化，0.60～0.79仅进程内候选，取消轮忽略；召回≤4条且≤800 token；Prompt不暴露FTS/vector等技术细节。
- 数据来源门仍固定为真实语音产生的session/turn；合同测试中的假embedding不形成E2E结论。
- 取消围栏在检索完成后再次检查；记忆抽取仅在标准记录会话结束后运行。开放P0/P1=0，允许执行B4.2真实验收。

## B4.2 结果与B4.3开发前审计

- 首次真实验收因复合查询未达0.55而FAIL，证据在 `audit/v1/B4/B4.2/`；未降低阈值。
- 修订为可审计的复合查询分句与口语填充词归一化；正式结果 `audit/v1/B4/B4.2-final/result.json`：5稳定事实、5临时候选、2条语义召回、6 token、无技术细节泄露，PASS。
- 测试记忆已以产品事务清理，source/FTS/vector/meta均为0；真实session/turn与失败证据保留。
- B4.3只在MemoryService/API层增加搜索、编辑、单删和全清；继续复用B4.1唯一事务边界。UI不得先行删除，全清缺少精确确认返回412。
- 审计事件只含action、hash、计数和结果，不含记忆正文；故障注入必须证明rollback且重试幂等。开放P0/P1=0，允许进入B4.3。

## B4.3 结果与B4.4开发前审计

- `audit/v1/B4/B4.3-edit-delete/result.json`：编辑后旧值0命中、新值命中；单删后精确/模糊/语义均0召回，四层同步。
- `audit/v1/B4/B4.3-purge/result.json`：缺确认返回412，全清5条、重试0条；三类故障注入完整回滚，`integrity_check=ok`。
- B4.4创建态none不创建sessions；内部ID使用独立高位命名空间，REST/WS只返回`0`与随机会话引用；中途切换先建立取消围栏再补偿删除。
- 补偿删除覆盖session/turn/transcript/summary及会话派生memory/FTS/vector/meta，审计不得含正文或可反推会话ID。开放P0/P1=0，允许进入B4.4。

## B4.4 结果与B4.5开发前审计

- 首轮 `audit/v1/B4/B4.4/result.json` 因浏览器首帧确认比较了内部ID与脱敏指标ID而FAIL，未签门；修复确认路径和异步任务名后重跑。
- 正式 `audit/v1/B4/B4.4-final/result.json`：创建态none与中途单向切换各5轮真实ASR/LLM/CosyVoice；10/10无错误，业务六层增量均0，WAL=0，音频文件增量0，公开事件内部ID命中0。
- 42项合同/故障测试通过；中途删除含安全删除与WAL TRUNCATE，繁忙状态显式返回，不伪称已清理。
- B4.5严格只扫描`sessions/turns/session_transcripts/session_summaries`，判定`expires_at < now`；长期记忆、资产、数据库、备份不在删除集合。失败整批回滚；低盘只阻断可重建缓存并告警，不误删用户数据。开放P0/P1=0，允许进入B4.5。

## B4.5 结果与B4.6开发前审计

- `audit/v1/B4/B4.5/result.json` 使用真实SQLite、FTS5、sqlite-vec和实际数据卷：29天/恰好30天保留，仅31天会话四类业务行被删；3条长期记忆及索引全部保留，过期来源引用安全置空。
- 三个事务故障点均抛错、整批数据不变并产生无正文`retention.failed`；成功后重跑删除0条，幂等通过。
- 实际卷剩余约882GiB；模拟9GiB时`cache_writes_allowed=false`且既有业务数据不删除；512维错误fail-closed。
- Gateway启动补偿扫描、每日本地03:00任务、手动运行/时钟查询端点已接线；生产重启后`next_scan_at=03:00+08:00`且磁盘状态真实。
- B4.6只做证据汇总、全量回归和B2/B2.5/B3真实烟测，不新增产品能力。第一次全量回归为305 PASS/1 FAIL/4 SKIP，失败是标准会话进程内事件ID类型回退；恢复整数合同后306 PASS/4 SKIP。开放P0/P1=0，允许进入B4.6。

## B4.6 总验收结果

- 后端全量：306 passed / 4 skipped；前端`npm run build` PASS。
- `audit/v1/B4/B4.6/regression-b3-lifecycle/`：3/3生命周期、四端口在线、临时音频新增0。
- `audit/v1/B4/B4.6/regression-b3-interrupt/`：Windows Chrome 153真实早/中/晚打断3/3，静音P95=1.7ms，Avatar零重连、旧音频0。
- `audit/v1/B4/B4.6/regression-b25/`：真实普通链3/3，首响P50=4649.583ms、P95=5350.201ms，≤7秒。
- B4.1～B4.5正式证据均PASS，失败样本均保留；B2 live Avatar已由本轮Chrome链实际消费，未出现降级。
- PRD检视无规格偏移，开放P0/P1=0。B4关闭；下一阶段只能先执行B5开发前验收标准与审计。
