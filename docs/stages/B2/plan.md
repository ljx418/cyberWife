# B2 详细开发计划：语音首响、数字人口型与降级恢复

**日期**：2026-09-25  
**前置门**：B1 PASS；V1.3 约16GB空闲内存预算已批准  
**目标体验**：角色回复能够尽早以克隆声音播放，数字人由同一音频时钟驱动；数字人故障不打断声音，恢复无需刷新页面。

## 基线纠偏

历史 M3 对比误把 `user_clip_v2.wav` 的真实内容“早上好，宝贝，快起床了，起来陪我玩”标为“今天天气不错，我想和你聊聊天”。旧 CosyVoice CER=76.92% 与旧 Qwen 优胜结论均作废。B2 必须使用正确逐字稿、同一参考音频、同一30条文本和同一 Faster-Whisper 复测；不得引用旧结论通过门禁。

## 实施实体

1. `application/sentence_scheduler.py`：按中文终止标点和长度边界调度语义短句，不拆数字、英文词和未闭合标点。
2. `application/media_pipeline.py`：异步执行 TTS，按20ms PCM帧产生音频主时钟、首包/RTF/队列指标；TTS失败显式退化为文字。
3. `adapters/{qwen_tts,cosyvoice_tts}_adapter.py`：统一正确的流式帧、取消和指标合同；默认模型由公平实测门禁决定，未达标则保留阻断状态。
4. `adapters/live_talking_adapter.py`：仅暴露 `open/push_audio/cancel/health/close`，上游地址只允许 loopback。
5. `workers/avatar/server/routes.py`：增加受限原始 PCM 注入、取消与媒体指标端点；不接收路径，不落盘音频。
6. `application/turn_pipeline.py` 与 Gateway：文本 final 后接入 MediaPipeline，发送 `reply.audio.chunk/media.state/media.metrics`；Avatar失败时音频继续。
7. `tests/b2/`：合同、故障注入、30条真实TTS、真实Avatar FPS、资源与隐私证据。

## 资源与调度策略

- 以物理32GB、空闲约16GB为目标机；项目 private bytes + WSL项目RSS≤14GB，宿主与WSL `MemAvailable` 均≥2GB，无持续 swap-in。
- 不同时常驻两个 TTS；候选对比按模型分时加载、释放并记录峰值。
- 音频是主时钟，Avatar推理慢时丢弃迟到视频帧，禁止反压音频播放。
- 队列全部有界；PCM仅存在内存，不写入项目、data、temp目录。

## 开发顺序

1. 添加失败合同测试：语义切句、PCM帧、loopback限制、音频时钟、队列上限、Avatar降级/恢复、日志脱敏。
2. 实现 MediaPipeline、LiveTalkingAdapter 与上游PCM/指标合同。
3. 接入 TurnPipeline/Gateway，完成真实一轮 `ASR→LLM→TTS→Avatar`。
4. 用正确参考文本执行 Qwen/CosyVoice 30条配对测试，输出可试听 WAV、CER、首包、RTF、资源CSV；仅合格模型可成为默认。
5. 运行真实Avatar FPS、进程终止/恢复、音频不中断验证，并完成PRD规格检视。

## 不在 B2

用户开口触发的400ms统一打断、100轮/1小时稳态属于B3；长期记忆、无记录和保留清理属于B4。B2只实现可供B3调用的 `cancel` 合同，不冒充打断验收完成。
