# cyberWife V1 后端开发与验收计划

**版本**：2.6
**日期**：2026-10-06
**状态**：B0～B5与B2.5功能计划、ARCH1、RES1及V1RC1自动化重签均完成；V1FINAL现场取证工具开发中
**目标**：在已通过 G-UX 的前端体验基础上，交付可一键启动、本地部署、无限多轮、可打断、带声音与数字人的 V1 后端。

## 1. 计划结论

V1不需要重写现有后端，也不需要微服务化。保留当前模块化单体、端口/适配器和本机外部GPU进程结构。B0～B5与B2.5定义的功能链路均已有实现和目标机证据；ARCH1、RES1和V1RC1也已关闭架构、资源与当前候选重签。剩余工作不再是产品功能开发，而是：

1. V1FINAL现场证据：用安装版Chrome自动绑定真实PCM、三轮完整turn、打断、接续、当前人物和Idle，人类只签Narrator与自然度；
2. 发布外部门：在全新Windows 11用户 + 干净WSL2环境从驱动/本地工件准备执行到一键启动，形成独立复现证据；
3. 文档冻结：消除历史阶段文件与当前权威状态的歧义，历史失败证据继续保留但不冒充当前结论。

前端交互体验已由用户在 2026-09-24 批准为满足 V1 验收，后续只允许做后端接线、错误合同适配和回归修复，不进行视觉重构。

## 2. 技术选择

| 决策 | V1 选择 | 不选择 | 理由与代价 |
|---|---|---|---|
| 应用架构 | Python 模块化单体 Gateway + 本机推理进程 | 微服务平台 | 单用户本机产品无需分布式治理；代价是 Gateway 必须严格控制阻塞任务 |
| 实时编排 | `asyncio` task group + 有界 queue + cancellation token | 外部消息队列 | 取消时延低、部署简单；代价是进程重启后队列不恢复，但 V1 会话允许结束 |
| 默认 TTS | CosyVoice2 FP16流式非TensorRT | TensorRT或双TTS常驻 | O3R真实Edge 30/30，P50/P95=5.567/6.392s且资源达门；Qwen为显式回退 |
| CosyVoice | ADR-008默认 adapter | TensorRT默认 | 正确逐字稿CER=0.71%；TensorRT尾延迟回退约9.8%而拒绝 |
| 数据 | SQLite WAL + FTS5 + sqlite-vec | 独立数据库服务 | 本机单用户足够；删除事务和备份更简单 |
| Avatar | LiveTalking/Wav2Lip + loopback H.264 WebSocket/WebCodecs | 跨WSL WebRTC、前端直接调用上游 API | Chrome复验证明ICE不可达；A2保持PCM主时钟并已通过三周期恢复 |
| 运行方式 | Windows + WSL2 原生进程 | Docker | 符合 V1 范围；容器化留 V2 |

## 3. 现有实体盘点

### 3.1 可复用

- `backend/cyberwife/domain/{conversation,profile,memory}.py`
- `application/{conversation_orchestrator,prompt_compiler,output_sanitizer,model_registry}.py`
- `adapters/{silero_vad,faster_whisper,llama_cpp,qwen_tts,cosyvoice_tts}_adapter.py`
- `infrastructure/{sqlite_repository,vector_index,asset_store,structured_logger}.py`
- `workers/avatar/` 中 LiveTalking/Wav2Lip 上游运行代码
- `ops/windows/{RuntimeLauncher,StartLlamaCpp,ResolveWindowsHost}.ps1`

### 3.2 必须修改

- `api_gateway.py`：B1 已实现二进制音频与服务端事件；B2.5 补阶段计量、缓存诊断和浏览器播放确认合同。
- `conversation_orchestrator.py` / `turn_pipeline.py`：B1/B2 已有真实链；B2.5 统一 generation 提交检查并接入严格缓存旁路。
- `media_pipeline.py` / `sentence_scheduler.py`：补浏览器首个非静音确认、三类分桶和首个可播分句 A/B。
- `llama_cpp_adapter.py` / `cosyvoice_tts_adapter.py`：保留端口语义，增加可回退 runtime profile；不得原地破坏已验证基线。
- `live_talking_adapter.py` / `H264WebSocketOutput` / `AvatarSession`：真实终止/恢复已通过；B3补打断时迟到generation丢弃。
- `workers/speech_worker/server.py`：B0/B1 已真实运行；扩展单TTS admission、engine健康与预热低优先级调度。
- `health_aggregator.py`：B0真实探针已通过；增加engine/cache/分段计量状态。
- `RuntimeLauncher.ps1`：B0生命周期已通过；增加加速profile预检与串行回退，不让缓存阻塞 interactive_ready。
- `SqliteRepository` / `VectorIndex`：补齐 session/turn/memory/audit/retention 实现和同事务边界。

### 3.3 必须新增

- `application/interruption_controller.py`
- `application/memory_service.py`
- `application/retention_service.py`
- `adapters/bge_embedding_adapter.py`
- `workers/speech_worker/scheduler.py`
- `domain/warm_response.py`
- `application/warm_response_cache.py`
- `infrastructure/runtime_metrics.py`
- 可选 `adapters/cosyvoice_tensorrt_adapter.py` 或等价 profile 实现；仅真机可行性通过后创建。
- 真实模型 integration/performance/privacy/e2e 测试与证据收集器。

## 4. 里程碑与开发顺序

### B0：可运行基线与合同修复

**完成后的用户效果**：执行一个 PowerShell 命令后，页面只在所有必要组件通过功能探针时显示就绪。

任务：

- B0-01 固定 Python、Node、模型 revision 和配置 schema；输出无秘密环境报告。
- B0-02 修复 `RuntimeLauncher.ps1` 参数、WSL Python 路径、工作目录、端口/PID 所有权和有序停机。
- B0-03 核验 9KB 薄启动器与同目录实现 DLL 的完整 llama.cpp bundle；实际完成 `--version`、`/health` 与一次流式 completion。只有功能探针失败才替换官方 bundle。
- B0-04 把 HealthAggregator 改为并行功能探针，记录 `last_probe/error/latency/device/dtype`。
- B0-05 启动 Gateway、SpeechRuntime、llama-server、Avatar 四类进程；失败时回滚本次启动的进程，不杀非本项目 PID。

出门门槛：

- `start` 连续执行两次只有一组实例；`stop` 连续执行两次均成功。
- 四类组件的 ready 均有真实最小推理证据；任一模型路径错误不得显示 ready。
- 启动失败后端口、PID 文件和临时音频残留为 0。

### B1：真实输入与 TurnPipeline

**完成后的用户效果**：开始对话后，真实麦克风音频能够产生用户 final 字幕和角色增量文本。

任务：

- B1-01 实现 WebSocket JSON 控制帧 + 20ms PCM 二进制帧解码、尺寸限制和背压。
- B1-02 建立 `SpeechRuntime`，串接 Silero VAD 与 Faster-Whisper；partial 只展示，final 才创建 turn。
- B1-03 建立 `TurnPipeline`：`audio→VAD→ASR final→PromptCompiler→LLM stream→OutputSanitizer`。
- B1-04 使用 `session_id/turn_id/event_seq/trace_id` 贯穿事件；迟到或跨轮事件 100% 丢弃。
- B1-05 每个阶段设置 deadline、有界 queue 和结构化指标，不在 event loop 内执行 GPU 阻塞调用。

出门门槛：

- 固定语料 20 轮至少 19 轮产生正确归属的 final 字幕与回答文本。
- 非法状态转换为 0；队列深度在输入停止后回落为 0。
- 日志可按 trace 定位一轮，但不包含完整音频、完整 prompt 或完整会话正文。

### B2：TTS、Avatar 与可听首响

**完成后的用户效果**：角色文本以克隆声音尽早播放，画面跟随同一音频时钟；Avatar 失败仍可语音聊天。

任务：

- B2-01 对Qwen/CosyVoice公平复测并按语义短句调度；只有完整首响门禁通过后才允许切换默认。
- B2-02 新建 `LiveTalkingAdapter`，只向上游暴露 `open/push_audio/cancel/health/close`。
- B2-03 音频播放时间戳作为口型主时钟；视频帧迟到即丢弃，不反向阻塞音频。
- B2-04 实现 TTS→文字、Avatar→静态肖像的显式降级与原地恢复。
- B2-05 记录 `utterance.final→first_audio`、TTS RTF、inferfps/finalfps、队列和 GPU/RAM 峰值。

出门门槛：

- 30 条普通缓存未命中语料首响 P95≤7.0s；P50如实报告但不设硬门。
- `inferfps` 与 `finalfps` 均≥25；VRAM≤22GB、项目非可回收RAM≤14GB，宿主/WSL可用内存均≥2GB。
- Avatar 进程终止后 2 秒内降级，音频不中断；恢复无需刷新页面。

### B2.5：B2 首响修复与安全预热（当前前置分支）

**调度说明**：尽管名称为 B2.5，当前必须在 B3 前执行，用于关闭真实首响 P1。B2.5 通过后先由 B2 签署 Avatar 恢复，B2 明确 PASS 后才执行 B3→B4→B5。

**完成后的用户效果**：普通问题说完后在既有硬门内听到回答；常用完整问候可更快开口；加速失败时原地回退且界面、声音质量和硬件门槛不退化。

任务：

- O1 浏览器端首响分段计量，普通未命中/严格命中/配置失效独立分桶。
- O2 验证首句调度、单slot和prompt cache等低风险优化。
- O3 通过稳定 `TtsPort` 验证 CosyVoice TensorRT profile，保留原adapter和Qwen回退。
- O4 经G-LAT7审查取消V1实施：达到7秒门后保留llama.cpp，不承担vLLM/TensorRT-LLM迁移成本。
- O5 增加≤64MiB、≤6项、完整句精确匹配的 `WarmResponseCache`；版本变化立即失效。
- O6 执行 OX-01～05、07、08、10～12；OX-09 交由 B2、OX-06 交由 B3 首次签署，B5 重跑 OX-01～12；任何所属门槛失败均停线。

详细开发合同、顺序、回滚与停线条件见 [`stages/B2.5/plan.md`](stages/B2.5/plan.md)，验收见 [`stages/B2.5/acceptance.md`](stages/B2.5/acceptance.md)。

### B3：统一打断与无限多轮稳定性

**完成后的用户效果**：用户开口后旧回答立即停止，新问题接管；多轮不会积压、串音或越来越慢。

任务：

- B3-01 新建 `CancellationToken(session_id, turn_id, generation)`，传播到 LLM、TTS、Avatar 与播放控制。
- B3-01A 先把Gateway改为持续receiver、单active-turn task、有界outbound queue和单sender，避免推理阻塞插话控制帧。
- B3-02 VAD 确认 barge-in 后并行取消所有下游 task，清空音频/帧队列并提升 generation。
- B3-03 所有 adapter 在产生 chunk 和执行副作用前检查 token；取消写入幂等。
- B3-04 注入迟到 token/audio/frame、慢推理、断连和重复 cancel。
- B3-05 运行 20 轮、100 轮工程压力和 1 小时用户稳态；观察内存、显存、任务数与延迟趋势。

出门门槛：

- 30/30 次打断回到 listening，VAD 命中到静音 P95≤400ms。
- 旧 turn 在打断后的音频、字幕、画面和记忆写入均为 0。
- 1 小时无崩溃/OOM/未处理任务；延迟、任务数和队列没有持续增长。
- 本阶段首次签署 OX-06；B5 在发布候选构建上重跑。

### B4：记忆、隐私与保留

**入口门**：B3 PASS；最终验收只能使用B3已`e2e_accepted`的真实session/turn。

**完成后的用户效果**：用户可以确认系统记住了什么、纠正或彻底删除，并能进行一次不可恢复的不记录会话。

任务：

- B4-01 实现 BGE embedding 和 FTS5+向量融合检索，限定 top-k、阈值与 prompt 预算。
- B4-02 实现候选记忆、置信度、来源、去重和用户编辑。
- B4-03 实现单删/全清事务：源记录、FTS、vector、摘要派生缓存同成同败。
- B4-04 将 no-record 策略置于持久化入口，覆盖 turn、transcript、summary、memory、vector。
- B4-04A 创建即none使用`2**62`起的进程内session ID；会话中开启先取消待写任务，再补偿删除整场业务记录，且不可逆。
- B4-04B MemoryRepository独占事务，VectorIndex不得内部commit；sqlite-vec不可用时fail-closed。
- B4-05 实现可注入时钟的 30 天清理、启动补偿、失败重试和低磁盘保护。

出门门槛：

- 删除后精确、模糊、语义查询命中均为 0；故障注入无半删状态。
- 不记录 5 轮后相关表、索引和数据目录增量均为 0。
- 时钟推进 31 天只删除过期会话文本/摘要，不删除长期记忆。

### B5：后端发布硬化与 V1 总验收

**完成后的用户效果**：核心链无公网依赖或联网上传动作，可一键启动并连续聊天；故障有可理解降级，退出后没有残留服务或隐私数据。

任务：

- B5-00 先补齐授权授予/撤销、资产版本列表/激活/回退、完整人设并发和沉浸式默认入口；这些是AC-01/02/11缺失实现，不得以总回归代替。
- B5-01 逐个终止 LLM/ASR/TTS/Avatar/Embedding，验证降级、重试和恢复。
- B5-02 按用户批准的替代方案运行核心路径：白盒检查出站动作，持续监测所有监听地址和项目进程连接；不执行会中断宿主终端的物理断网脚本。
- B5-03 跑完整 AC-01～AC-14；前端只做合同回归，不重新设计。
- B5-03A 重跑 OX-01～12，验证首响/缓存、Avatar恢复和打断组合后均无回退。
- B5-04 归档环境、模型哈希、JUnit、性能 CSV、脱敏日志摘要和场景视频。
- B5-05 冻结依赖/配置/数据库 schema，完成安装、备份、恢复、卸载和删除手册。
- B5-06 实现 [`acceptance-command-manifest.md`](acceptance-command-manifest.md) 中固定的 runner、退出码和证据 schema；模块缺失时状态只能是 NOT EXECUTED，禁止总是返回0的占位脚本。

出门门槛：

- AC-01～AC-14 全部 Pass；开放 P0/P1=0。
- 仅 loopback 监听，未声明出站请求=0，原始麦克风音频落盘=0。
- 一键 `start/status/recover/stop` 全部通过，目标硬件 1 小时稳态通过。

## 5. TTS 决策终态

ADR-008已确定非TensorRT CosyVoice2为V1默认，Qwen3-TTS为显式受保护回退，禁止双TTS常驻。TensorRT路线和高成本LLM运行时迁移不进入V1；B5在发布候选上重跑质量、资源和回退合同。固定中文语料仍要求CER≤5%、普通链P95≤7秒、30次无hang、VRAM/RAM达门和授权声音盲听≥4/5。

## 6. 自动化开发批次

每个批次都必须遵循：先写失败测试 → 最小实现 → 合同/集成测试 → 真实模型 smoke → 证据归档 → 对照本里程碑出门。禁止仅凭 mock 测试把任务标为完成。

| 批次 | 允许修改范围 | 必须产生的证据 |
|---|---|---|
| DEV-B0 | ops、server、health、config | launcher transcript、进程/端口快照、真实 probe |
| DEV-B1 | gateway、speech worker、turn pipeline | 20 轮事件流、状态/队列/trace 报告 |
| DEV-B2 | qwen adapter、avatar adapter、media contracts | latency.csv、FPS、A/V 录屏、资源曲线 |
| DOC/DEV-B2.5 | metrics、runtime profile、可选TensorRT adapter、严格内存缓存 | 普通/命中分桶CSV、质量、资源、负例、回退证据 |
| DEV-B3 | cancellation、queue、fault tests | 30 次打断、100 轮压力、1h soak |
| DEV-B4 | memory、repository、retention | 删除事务、不记录、31 天时钟报告 |
| DEV-B5 | recovery、privacy、release docs | AC-01～14 总报告和发布清单 |

## 7. 停线规则

- 出现原始音频落盘、非 loopback 监听、敏感正文进入日志：立即停止后续开发并清理证据。
- 真实链路VRAM>22GB、项目private bytes+RSS>14GB、宿主/WSL可用内存<2GB或持续swap-in：先执行既定分时卸载/缓存降级；仍超限则停止发布。
- 默认模型 CER>5%、20 轮成功率<95%、打断 P95>400ms、首响 P95>7.0s：不得跨里程碑。
- 任何为了通过测试而降低 PRD 门槛、改成 mock、跳过真实模型的变更：视为验收失败。
- 前端视觉变更必须另行获得范围批准；后端接线不得借机重构已批准体验。
