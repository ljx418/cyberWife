# B2.5 本机实时体验优化目标架构

**版本**：1.0  
**日期**：2026-09-25  
**状态**：DOC-O 候选；等待人类架构方向批准

## 1. 决策

采用“稳定端口 + 可替换运行时 profile + 非持久化严格缓存”的渐进优化，不重写 Gateway，不改变既有 UI 路由，不改变 SQLite schema。先做计量和低风险流水线优化，再验证 CosyVoice TensorRT；LLM 运行时迁移是条件分支，不是预设结果。

拒绝把 TensorRT、vLLM 或问候缓存直接写进 `TurnPipeline`。应用层只依赖 `LlmPort/TtsPort/AvatarPort/WarmResponsePort`；具体引擎在 composition root 选择。

## 2. 代码实体与状态

| 实体 | 路径 | 当前 | B2.5动作 |
|---|---|---|---|
| `ApiGateway` | `backend/cyberwife/application/api_gateway.py` | B1已开发 | 扩展阶段详情、缓存诊断和浏览器播放确认合同 |
| `TurnPipeline` | `backend/cyberwife/application/turn_pipeline.py` | B1/B2已开发 | 统一generation检查；接入严格缓存端口；保留普通主链 |
| `MediaPipeline` | `backend/cyberwife/application/media_pipeline.py` | B2已开发 | 将首响结束点固定为浏览器非静音确认，不以服务端yield冒充 |
| `SentenceScheduler` | `backend/cyberwife/application/sentence_scheduler.py` | B2已开发 | A/B首个可播分句，不降低文本边界质量 |
| `LlamaCppAdapter` | `backend/cyberwife/adapters/llama_cpp_adapter.py` | B1已开发 | profile化单slot/prompt cache；保持stream/cancel合同 |
| `CosyVoiceTtsAdapter` | `backend/cyberwife/adapters/cosyvoice_tts_adapter.py` | B2候选 | 保留原路径；新增TensorRT profile/adapter，不原地破坏 |
| `QwenTtsAdapter` | `backend/cyberwife/adapters/qwen_tts_adapter.py` | 默认基线 | 保留回退，不双常驻 |
| `LiveTalkingAdapter` | `backend/cyberwife/adapters/live_talking_adapter.py` | B2已开发 | 继续以PCM时间戳为主时钟，检查generation |
| `WarmResponsePolicy` | `backend/cyberwife/domain/warm_response.py` | 未开发 | 纯规则：规范化、完整句白名单、版本键、不变量 |
| `WarmResponseCache` | `backend/cyberwife/application/warm_response_cache.py` | 未开发 | ≤64MiB内存LRU；PCM/文本派生物；无持久化 |
| `RuntimeMetrics` | `backend/cyberwife/infrastructure/runtime_metrics.py` | 指标分散 | 新增统一阶段、命中分桶、资源采集 |
| `AccelerationProfile` | `backend/cyberwife/application/runtime_config.py` | 通用配置已存在 | 新增可回退选择，不允许客户端任意路径或engine参数 |

上述新增路径是开发合同，不代表文件已存在。实际开发前必须用失败测试锁定接口。

## 3. 正常、命中与打断数据流

### 普通未命中

`asr.final → WarmResponsePolicy MISS → PromptCompiler → LlmPort.stream → SentenceScheduler → TtsPort.stream → Browser first_non_silent → AvatarPort.push_audio`

MISS 检查必须是内存纯计算，不得阻塞或等待后台预热。普通路径单独计算 P50/P95。

### 严格命中

`asr.final → normalize exact sentence → versioned cache HIT → cached text + PCM → Browser + Avatar`

主屏只表现自然的 `thinking/speaking`；命中信息只进入运行状态二级诊断和脱敏指标。

### 打断

`barge_in.detected → generation++ → cancel LLM/TTS/Avatar tasks + browser purge → listening → 新turn重新判定`

缓存PCM也必须绑定 generation；旧缓存播放和普通生成具有相同的清除义务。

## 4. 引擎隔离与回退

- Cosy TensorRT engine 由固定模型revision、CUDA、TensorRT、精度和目标GPU共同决定缓存键；任一不符即拒绝加载。
- engine 存在、反序列化成功和一次合成都只是功能探针；ready 还要求可解码音频和资源界内。
- vLLM/TensorRT-LLM 必须实现既有流式、取消、健康和deadline合同；若改变提示词语义或输出清洗边界则不准接入。
- 加速器失败不得自动同时拉起另一套常驻模型。先释放失败运行时，再串行加载回退，状态显示准备中/已降级。
- 回滚不迁移数据库；删除engine、缓存PCM和profile即可恢复。

## 5. 资源调度

- 项目私有内存+WSL RSS≤14GB，WarmResponseCache硬上限64MiB；不是额外放宽。
- VRAM≤22GB；预留浏览器、显示驱动和瞬态峰值，不以平均值验收。
- SpeechRuntime同时最多一个TTS生成；后台预热只有在无active turn、两侧可用内存≥2GB且无swap-in时运行。
- `interactive_ready` 只等待正常链核心功能探针，不等待完整问候缓存。
- 缓存最多6项实际PCM，按LRU回收；磁盘零写入。

## 6. ADR取舍

| 方案 | 优点 | 代价/风险 | 决策 |
|---|---|---|---|
| llama.cpp低风险profile | 迁移最小、取消合同已有 | 收益可能不足 | 第一优先 |
| CosyVoice TensorRT | 可能降低TTS首包且现有CER好 | engine兼容、构建时间、算子支持风险 | 受控验证 |
| vLLM | 吞吐成熟、服务化清晰 | 单用户低并发收益不确定、额外显存/依赖 | 条件候选 |
| TensorRT-LLM | 潜在最低LLM延迟 | 构建复杂、版本耦合、回滚成本最高 | 最后候选 |
| 严格问候预热 | 高频招呼首响显著降低 | 错误命中会破坏语义与信任 | 小白名单、独立统计 |

## 7. 架构不变量

1. 无论使用何种引擎，普通路径硬门不变。
2. 任何chunk和副作用在提交前检查generation。
3. 缓存不处理天气、记忆、开放问题或带附加语义句子。
4. 缓存和engine是可删派生物；源模型、用户资产和数据库不被改写。
5. 所有监听仍为loopback，断网可构建后的运行必须通过；运行期不得自动下载。
6. 前端主路由、六态和主操作不变；只有局部阶段说明和二级诊断允许变化。
