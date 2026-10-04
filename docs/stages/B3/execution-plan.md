# B3 执行计划、验收门与审计闭环

**状态**：APPROVED FOR IMPLEMENTATION（2026-09-25）  
**范围**：只实现 B3 全双工会话、统一打断、旧 generation 隔离和长稳态；不提前实现 B4/B5。  
**前置证据**：B2、B2.5 PASS；`audit.md` 开放 P0/P1=0；用户已批准后续自动化开发。

## 实施顺序

1. 先建立 `CancellationToken`、`InterruptionController` 与幂等取消合同。
2. 把 Gateway 改造成持续 receiver、单 active turn、单 sender、有界 outbound queue。
3. 为 LLM、TTS、Avatar、持久化和 WebSocket 输出增加 generation fence。
4. 浏览器只取消旧 generation 的播放与 Avatar 帧，不关闭麦克风输入。
5. 执行故障注入、30 次真实打断、100 轮真实语音压力和 1 小时 soak。

## 本阶段验收标准

- 同一 session 任意时刻最多一个 active turn；断连、结束或取消后 task/queue 回到 0。
- 30 次早/中/晚打断全部回到 listening，用户出声到旧音频静音 P95≤400ms。
- 被取消 generation 的字幕、音频、Avatar 帧和持久化增量均为 0。
- 100 轮成功率≥95%；1 小时无崩溃、OOM、持续 swap-in 或资源/延迟单调增长。
- B2 Avatar 恢复与 B2.5 普通首响烟测不回退；项目 RAM≤14GB、VRAM≤22GB。

## 开发前独立审计意见

| 检查项 | 结论 | 处理 |
|---|---|---|
| PRD FR-07/08/09/10 与 NFR-01/02/03/06/07 映射 | PASS | 使用 `acceptance.md` B3-AC01～07 |
| receiver 被推理阻塞 | P1 已关闭 | 强制 SessionRuntime，不在 receive loop 等待推理 |
| asyncio cancel 无法停止底层线程 | P1 已关闭 | adapter cancel + token + generation fence 三层隔离 |
| 多协程并发写 WebSocket | P1 已关闭 | 所有事件只进入单 sender queue |
| 以 mock 冒充出门 | P1 已关闭 | mock 只用于合同回归；出门必须目标机真实模型与 Chrome |
| 前端体验漂移 | PASS | 仅接线、取消与错误合同，不改变 G-UX 视觉结构 |

**审计结论**：无开放 P0/P1，允许进入 B3 实质开发；任一真实硬门失败则退回本文件修订，禁止进入 B4。
