# B2.5-O1 可观测性基线开发计划

**日期**：2026-09-25  
**状态**：开发前计划已锁定

## 1. 目标与边界

O1 只建立可复跑的真实首响测量链，不修改 ASR、LLM、TTS、Avatar 的模型、提示词、调度阈值或默认运行时。测量口径固定为服务端 ASR final 到浏览器音频设备调度的首个非静音 PCM 样本。

允许修改的实体：

- `RuntimeMetrics`：保存脱敏阶段时间点、generation、分桶、原始样本和 P50/P95；
- `TurnPipeline`：写入 ASR final、LLM 首个可播片段、TTS 首包时间点；
- `ApiGateway`：接收浏览器播放确认并输出运行指标；
- `ConversationClient` / `MediaSession`：在浏览器解码 PCM、检测首个非静音帧并回传确认；
- 对应单元、合同、集成和浏览器测试，以及 O1 真实验收脚本。

明确禁止：TensorRT/vLLM、问候缓存、SentenceScheduler 阈值调优、模型切换、数据库迁移、主界面或路由调整。

## 2. 实施顺序

1. 先写失败测试，锁定 `trace_id/session_id/turn_id/generation/bucket` 和四个时间点合同。
2. 实现有界、线程安全、无原文落盘的 `RuntimeMetrics`；样本缺少浏览器确认时不得计入完整首响分位数。
3. 在 `TurnPipeline` 标记 ASR final、首个可播片段和 TTS 首包；所有本轮事件带同一 generation。
4. Gateway 接受 `audio.playback.started` 控制帧，校验当前 generation；旧 generation、未知 trace 或重复确认不得污染新轮。
5. 浏览器 `MediaSession` 以 16kHz/mono/int16 合同接收分片；首个超过静音阈值的样本进入播放调度后，仅回传一次确认。
6. 输出 normal/cache-hit/config-invalid 独立分桶；O1 只生成 normal 数据，另两桶必须保持空，禁止伪造缓存效果。
7. 跑后端全回归、前端构建和真实模型 30 条普通语料；保存 CSV、脱敏 JSON、资源快照与命令。

## 3. 数据合同

每条样本至少包含：`trace_id`、`session_id`、`turn_id`、`generation`、`bucket`、`asr_final_ms`、`llm_playable_ms`、`tts_first_packet_ms`、`browser_first_non_silent_ms`、分段耗时和 `complete`。不得包含用户输入、模型回复、人设、记忆、音频或本地绝对路径。

浏览器回传字段为本轮标识、浏览器检测到的首非静音 wall-clock 和 `asr_to_playback_ms`。完整耗时由服务端随首个音频分片下发的单调时钟阶段耗时，加上浏览器从收到该分片到 AudioWorklet 渲染的本地 `performance.now()` 差值组成；禁止直接相减 Windows/WSL wall-clock。后端只接受有限数值范围，避免确认处理延迟污染结果。

## 4. 回滚

`RuntimeMetrics` 是进程内有界派生数据；移除注入或关闭浏览器确认即可恢复原链路。失败不得写入 SQLite，不改变用户数据和模型资产。新增测量字段保持 WS envelope 六字段不变。

## 5. 完成定义

O1 只有在 O1 验收标准全部通过、真实 30 条证据存在、PRD 复检无重大偏差、开放 P0/P1=0 后才能进入 O2。普通路径仍不满足最终首响门不阻止进入 O2，因为 O1 的目的正是可信地量化该差距；但计量不完整、错绑 generation 或资源越门必须停线。
