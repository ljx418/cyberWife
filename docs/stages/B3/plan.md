# B3 详细开发计划：统一打断与无限多轮稳定性

**状态**：PLANNED；尚未进入产品代码开发  
**前置门**：B2、B2.5 PASS；B3 文档审计 P0/P1=0  
**目标体验**：角色说话时用户自然开口即可在 P95 400ms 内停止旧声音，立即回到倾听；长期聊天不存在串轮、越积越慢或必须刷新页面。

## 1. 当前事实与断点

- Gateway 在 `audio.silence` 后同步遍历 `TurnPipeline.run()`，同一 WebSocket 在本轮结束前不能继续接收插话控制帧。
- Orchestrator 只有 generation 计数，没有可传播、可等待、可幂等取消的 token。
- LLM/TTS producer 使用线程与队列，取消 asyncio task 不等于停止底层生成。
- `MediaSession` 没有保存已调度的 `AudioBufferSourceNode`，只能关闭整个 AudioContext，可能同时破坏麦克风输入。
- Avatar 已通过故障恢复，但尚未按 generation 清理打断后的音频与视频帧。

## 2. 固定架构

每个 session 建立一个 `SessionRuntime`：持续接收任务、最多一个 active turn task、一个有界 outbound queue、一个串行 WebSocket sender。接收任务不得等待模型推理；所有服务端发送都经 sender 排序。

`CancellationToken` 固定字段为 `session_id/turn_id/generation/reason/cancelled_at`，内部持有可等待 event。`InterruptionController` 是唯一的 generation 提升和跨组件取消入口；重复 cancel 返回同一结果，不再次产生副作用。

有效 barge-in 后并行执行：标记 token、关闭 LLM stream、停止 TTS、清空 Gateway 音频队列、停止浏览器旧 source、flush Avatar talk/视频队列。最后发布 `turn.cancelled`；任一组件超过 1000ms 进入明确 degraded，但 session 保持 listening。

## 3. 开发子阶段

1. **B3.0 可取消媒体基础**：为已调度 `AudioBufferSourceNode` 建立 `generation → Set<source>` 注册表；先写 cancel/重复cancel/输入不中断合同；统一 monotonic ns 与 wall-clock correlation。
2. **B3.1 全双工 Gateway**：保持旧半双工回归绿灯后，引入 SessionRuntime、单 sender、有界队列、断连清理和 WS 并发合同测试；以 feature flag 分步切换。
3. **B3.2 统一取消**：新增 CancellationToken/InterruptionController；LLM、TTS、Avatar、TurnPipeline 和持久化边界执行 generation fence。
4. **B3.3 浏览器与 Avatar 清理**：`MediaSession.cancelGeneration()` 只停止旧播放；`AvatarSession` 丢弃旧 generation 帧；麦克风监听不暂停。
5. **B3.4 迟到与故障注入**：覆盖慢 LLM、慢 TTS、Avatar 迟帧、重复 cancel、断连和 cancel timeout。
6. **B3.5 真实验收**：按 [`../../acceptance-command-manifest.md`](../../acceptance-command-manifest.md) §2 执行 Chrome 30 次打断、100 轮压力、1 小时 soak，完成 PRD 检视。

每个子阶段先更新 `acceptance.md` 的场景和证据目录，再执行合同测试、实现、真实 E2E、PRD 检视；任一 P0/P1 返回计划阶段。

## 4. 未来代码实体

- 新增：`domain/cancellation.py`、`application/interruption_controller.py`。
- 修改：`api_gateway.py`、`conversation_orchestrator.py`、`turn_pipeline.py`、`media_pipeline.py`。
- 补取消合同：LLM/TTS/Avatar ports 与 adapters。
- 浏览器合同：`ConversationClient`、`MediaSession`、`AvatarSession`、`ConversationScreen` reducer。
- 验收工具：`tests/b3/` 与 `audit/v1/B3/`。

## 5. 不变量与停止条件

- 同 session 最多一个 active turn；所有 queue 有界且取消/结束后回到 0。
- 旧 generation 的字幕、音频、帧、转录完成、摘要和记忆候选均不得传播。
- 400ms 是用户听感门，1000ms 只是组件回收 deadline，禁止混用。
- 不新增常驻模型；沿用约 16GB 空闲、项目 RAM≤14GB、VRAM≤22GB 的预算。
- 若 30 次打断、资源或隐私任一硬门失败，B3 停线，不进入 B4。
