# B4 验收标准：记忆、删除、不记录与保留

**状态**：PASS（2026-09-26）  
**数据要求**：只接受 B3 已通过的真实 session/turn；mock 仅用于故障注入。
**执行入口**：[`../../acceptance-command-manifest.md`](../../acceptance-command-manifest.md) §3；当前 runner 尚未实现，禁止用内存替身形成通过结论。

| ID | 用户场景与操作 | 证据 | 硬门 |
|---|---|---|---|
| B4-AC01 | 说出5条稳定事实和5条临时/低置信内容，结束后新会话询问 | 候选/固化/召回报告 | 稳定事实可追踪并召回；低置信不固化 |
| B4-AC02 | 关键词、改写和语义相关查询 | FTS/vector/fusion 原始排名 | 合格记忆进入≤800 token预算；无技术细节泄露给用户 |
| B4-AC03 | 编辑一条记忆后检索旧/新值 | DB/FTS/vector diff | 旧值0命中；新值可命中；edited=true |
| B4-AC04 | 单删并做精确、模糊、语义检索 | 四层计数与查询报告 | source/FTS/vector/cache全部0召回 |
| B4-AC05 | 二次确认全清，注入中途失败后重试 | transaction/audit/integrity报告 | 成功时全0；失败时全回滚；重试幂等 |
| B4-AC06 | 启用no-record完成5轮、重启并搜索 | 前后表计数、文件与日志扫描 | session/turn/summary/memory/vector增量0；音频文件增量0 |
| B4-AC07 | 标准会话中途开启no-record | 取消与补偿删除事件、DB/WAL/audit/loopback抓包 diff | 整场业务数据归零；内存ID不进入envelope/audit/error；之后不可恢复记录 |
| B4-AC08 | 注入29/30/31天数据并运行保留任务 | 可控时钟和行级报告 | 仅>30天文本/摘要删除；长期记忆保留 |
| B4-AC09 | sqlite-vec不可用、维度错误、低磁盘 | health/error/文件报告 | 关闭sqlite-vec后必须非ready；不得内存/FTS冒充；低水位仍不产生no-record业务写入；无误删 |

全部通过并且开放 P0/P1=0，方可签署 AC-07～10 和 AC-13 数据部分并进入 B5。

资源趋势采用命令清单 §5 的量化斜率；低磁盘采用 `~/.cyberWife` 所在卷的可用空间，不以目录逻辑大小代替。

## 实际结果

| ID | 结果 | 证据 |
|---|---|---|
| B4-AC01/02 | PASS；5条稳定事实固化、5条临时候选不固化，两类语义召回，prompt 6 token | `audit/v1/B4/B4.2-final/result.json` |
| B4-AC03/04 | PASS；编辑旧值0/新值命中；单删后三种查询0召回、四层同步 | `audit/v1/B4/B4.3-edit-delete/result.json` |
| B4-AC05 | PASS；412确认、全清、三故障点回滚、重试幂等 | `audit/v1/B4/B4.3-purge/result.json` |
| B4-AC06/07 | PASS；两种策略共10轮真实链；业务增量/WAL/音频文件/内部ID泄漏均0 | `audit/v1/B4/B4.4-final/result.json` |
| B4-AC08/09 | PASS；仅31天过期，长期记忆3/3保留；低盘阻断缓存、维度错误拒绝 | `audit/v1/B4/B4.5/result.json` |

全量后端回归306 PASS/4条件跳过；前端生产构建PASS；Windows Chrome早/中/晚打断3/3、P95=1.7ms；普通首响3/3、P95=5350.201ms。开放P0/P1=0。
