# B3 自动化开发与验收审计记录

**执行日期**：2026-09-25  
**当前状态**：PASS；B3 已关闭，可进入 B4 开发前阶段门。

## 已闭环实现

- `CancellationToken`、`InterruptionController`、`SessionRuntime` 已形成单一取消入口、持续 WS receiver、单 sender 与有界队列。
- LLM、TTS、浏览器音频、Avatar H.264 和 SQLite 写入均受 generation fence 约束。
- 浏览器取消只停止旧 `AudioBufferSourceNode`，不关闭共享 `AudioContext`；服务端以 `audio.playback.ended` 结束 speaking 生命周期。
- Avatar WebCodecs 在显式硬件解码不可用时回退浏览器自选解码；generation 切换强制 H.264 关键帧，取消后不重连。
- 旧轮延迟 cancel 必须携带匹配的 `turn_id`，否则不得取消新轮；已生成文本但仍播放的轮次被打断后持久化状态改为 `cancelled`。
- 取消 hook 设 900ms deadline；超时明确进入 `component_errors`，会话仍恢复 listening。

## 真实失败、退回与修订

第一次 B3-AC05 在 19 轮内出现多次 `media.state=static_fallback`，失败率超过 5%，已主动中止，未签 PASS。证据保留于 `audit/v1/B3/AC05/turns.partial.json`。

根因是 Avatar 逐帧 loopback 注入的单次瞬时超时会禁用整轮 Avatar。修订为：单个或非连续失败只丢弃对应 20ms 唇形帧并计数；连续 3 次失败才在约 1.05 秒内明确降级。该修订不改变浏览器音频主时钟、不增加常驻模型、不提高 RAM/VRAM 门槛。修订后 20 轮真实诊断为 20/20 PASS，证据在 `audit/v1/B3/AC05-diagnostic-v2/`。

## 已完成验收

| 验收项 | 真实结果 | 证据 | 判定 |
|---|---|---|---|
| B3-AC01 | Windows Chrome 153；早/中/晚各10次；30/30；静音 P95=1.7ms；Avatar 零重连 | `audit/v1/B3/AC01/` | PASS |
| B3-AC02/03 | 旧 generation 事件0；取消轮 DB 无后续变化；新轮真实转录/回答匹配 | `audit/v1/B3/AC02-03/` | PASS |
| B3-AC04 | 重复取消、断连、慢组件 deadline 3/3 | `audit/v1/B3/AC04/` | PASS |
| B3-AC05 | 正式100/100，成功率100%，严格事件序，live Avatar无媒体降级 | `audit/v1/B3/AC05/` | PASS |
| B3-AC06 | 真实60分钟、721采样、20完整轮+10打断；资源、任务、队列与swap均过门 | `audit/v1/B3/AC06/` | PASS |
| B3-AC07 | 3/3 生命周期；无新增临时音频，task/queue归零 | `audit/v1/B3/AC07/` | PASS |
| B2.5回归 | 真实 Chrome 三轮，首响P95=4347.646ms | `audit/v1/B3/regression-b25-final/` | PASS |
| B2回归 | 真杀进程后604ms静态降级，同页面恢复25 FPS并完成下一轮 | `audit/v1/B3/regression-b2-recovery/` | PASS |

## 当前审计结论

本轮发现的旧轮误取消、播放期 DB 状态、WebCodecs 解码选择、H.264 关键帧恢复及 Avatar 瞬时超时五项 P1 均已有代码、合同回归和真实证据。全量后端269 passed/4 skipped、Avatar worker 3 passed、前端构建 PASS。开放 P0/P1=0，B3 出门签署完成。
