# B1 详细开发计划：真实输入与 TurnPipeline

**日期**：2026-09-24  
**前置门**：B0 PASS；V1.3约16GB可用内存预算已批准  
**目标体验**：用户送入真实16kHz单声道PCM后，系统只在有效语音形成final时创建一轮，并持续返回归属正确的用户字幕与角色增量文本。

## 实施实体

1. `workers/speech_worker/server.py`：增加有界原始PCM utterance API，lazy/warm加载Silero VAD与Faster-Whisper，保留segment时间戳，禁止音频落盘。
2. `adapters/faster_whisper_adapter.py`：输出segment start/end/confidence，校验16kHz mono PCM，空音频/奇数字节拒绝。
3. `adapters/speech_runtime_client.py`：Gateway到loopback SpeechRuntime的超时受控客户端。
4. `application/turn_pipeline.py`：ASR final、PromptCompiler、LLM stream、OutputSanitizer的异步流水线；GPU/CPU阻塞调用均离开event loop。
5. `application/conversation_orchestrator.py`：session内单调turn、generation、迟到事件抑制和合法状态转换。
6. `application/api_gateway.py`：补`POST/DELETE sessions`、真实WS文本控制帧与646字节二进制音频帧、尺寸/顺序/背压/错误合同。
7. `infrastructure/sqlite_repository.py`：标准记录模式持久化session/turn；no-record不在B1提前宣称完成，只保留合同入口。
8. `config/*.toml`：固定30秒utterance、20ms/640字节帧、每连接最大缓冲、ASR/LLM deadline与有界队列。

## 资源策略

- Gateway不加载推理模型；SpeechRuntime只常驻B1所需VAD+ASR。
- B1不加载TTS或Embedding；Avatar可运行但不参与文本链关键路径。
- ASR优先GPU float16；若目标运行时实测不支持则使用CPU int8，但必须记录RTF且不得伪称达到实时门槛。
- 项目可归因RAM≤14GB、WSL `MemAvailable≥2GB`、无持续swap-in；队列必须有硬上限。

## 开发顺序

1. 先添加失败合同测试：帧解析、乱序/跨轮、超限、final唯一建turn、状态机、日志脱敏。
2. 实现SpeechRuntime真实utterance API及单元/集成测试。
3. 实现TurnPipeline与session API/WS接线。
4. 完成20轮真实授权音频→真实ASR→真实LLM文本E2E。
5. 采集队列、状态、trace、RAM/VRAM和临时文件证据；执行PRD规格检视。

## 不在B1

TTS、Avatar音频驱动、打断400ms、长期记忆、保留清理和1小时稳态分别属于B2～B5，不得在B1验收中冒充完成。
