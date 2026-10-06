# cyberWife V1 后端目标架构

**版本**：2.8
**日期**：2026-10-06
**状态**：B0～B5、B2.5、UX4、UX5、ARCH1、RES1与V1RC1自动化门已有目标机证据；V1FINAL现场报告与INST1-AC07当前revision报告待闭环
**架构风格**：模块化单体 Gateway + 端口/适配器 + 本机 GPU 推理进程

## 1. 架构结论

V1 保持单用户、本机原生、无 Docker。Python App Gateway 是业务和一致性中心；LLM、Speech、Avatar 是因运行环境和 GPU 调度不同而分离的本机进程，不是独立业务微服务。领域规则不能进入模型 adapter，外部推理接口必须由端口隔离。

```text
已验收 Browser UI
  │ REST / WebSocket（二进制 20ms PCM + JSON 控制/事件）
  ▼
App Gateway :7860
  ├─ SessionApplication / TurnPipeline / InterruptionController
  ├─ MemoryService / RetentionService / HealthAggregator
  ├─ SQLite WAL + FTS5 + sqlite-vec + private AssetStore
  ├─ HTTP stream/cancel → Windows llama-server :8090
  ├─ IPC/loopback → WSL SpeechRuntime :8091（VAD/ASR/Embedding，受控Core venv）
  ├─ in-process adapter → CosyVoice2默认 / Qwen3-TTS显式回退
  └─ HTTP PCM → WSL AvatarRuntime :8010（LiveTalking/Wav2Lip）
                              │ loopback WS / Annex-B H.264
                              └────────────────────► Browser WebCodecs/canvas

RuntimeLauncher.ps1 负责 start / status / recover / stop 与真实功能探针
```

完整可探索图见 [`../review/cyberwife-v1-stage-audit-architecture.html`](../review/cyberwife-v1-stage-audit-architecture.html)，当前权威可编辑总图见 [`../cyberWife-b3-b5-delivery-gap.drawio`](../cyberWife-b3-b5-delivery-gap.drawio)。`cyberWife-architecture-gap.drawio`仅为开发前历史基线。

## 2. 现状与目标差距

| 层 | 当前仓库事实 | V1 目标 | 状态 |
|---|---|---|---|
| 前端 | G-UX/G-OX体验已获批准；已有 ConversationClient/MediaSession | 只做真实事件接线、局部阶段反馈与回归修复 | 已验收/冻结 |
| API | 二进制音频、真实事件链、session/memory/health/asset/profile API均已实现；具体仓储、资产存储和日志只在组合根注入 | 保持合同稳定与单向依赖 | 已开发/ARCH1验收通过 |
| 会话领域 | Session/Turn 六态、event_seq、持久化和迟到判断已实现 | 领域状态不持有 GPU task | 已开发/已验收 |
| 实时编排 | 异步TurnPipeline、分句、媒体流水线、统一取消与generation清理已实现 | 保持有界队列和取消合同 | 已开发/已验收 |
| VAD/ASR | SpeechRuntime真实进程与20轮final合同通过；UX8统一繁简/普通话词形与segment展示 | Chrome 900ms句中停顿端点，保持20ms流式输入与不落盘 | 已开发/机器验收；物理麦克风复验待签 |
| LLM | Windows llama.cpp真实stream、低风险profile与跨阶段取消已通过 | 不迁移高成本runtime | 已开发/已验收 |
| TTS | Cosy默认链30/30、普通链P95≤7秒、授权盲听5/5；统一取消已接入 | Qwen保留显式回退 | 已开发/已验收 |
| Avatar | H.264/WebCodecs全链、打断清队列、降级/恢复与长稳态通过；UX5 A/V量化及用户视觉批准已完成 | 保持动态形象逐素材人工确认门 | 已开发/已验收 |
| 人物生成 | Qwen Image正面化→Wan Idle→10秒闭环→双预览→人工确认→Wav2Lip数据构建；文件任务状态可恢复 | 逐素材人工身份/自然度签署 | 已开发/人工门持续执行 |
| 数据 | SQLite/FTS/sqlite-vec、Memory/Retention、原子删除与no-record均已实现 | 保持事务与保留策略 | 已开发/已验收 |
| 健康 | 六组件真实probe、资源、engine、缓存与首响分段状态已实现 | 保持真实状态，不以文件存在冒充ready | 已开发/已验收 |
| 启动 | audit/prepare/verify与start/status/recover/stop已实现；AC06R以本地制品清单生成本机模型注册表、私有参考音频/Avatar/Cosy源码，Gateway和Launcher不再依赖开发机硬编码素材；双身份拒绝和五项空状态约束新环境 | 在真实新Windows用户+干净WSL运行已完成的执行器 | 当前机迁移/真实启停PASS；外部环境待验 |
| 验收 | V1FINAL现场报告绑定Git revision；AC09总门复算完整源码、依赖、前端和证据SHA，并校验现场/部署报告同提交；部署策略显式区分AC07同机隔离与AC06独立机 | 现场关闭UX6主观、结构化物理麦克风、人工Narrator；同机生成AC07报告 | 聚合器与AC07执行器已开发/真实报告待生成 |

## 3. 目标代码实体

状态说明：`[保留]` 已有且职责基本正确；`[已开发]` 已有真实阶段证据；`[修改/扩展/优化]` 已有但后续合同不完整；`[新增]` 当前不存在；`[上游]` 外部代码只经 adapter 使用。

```text
backend/cyberwife/
├─ api/
│  └─ server.py                              [修改] 仅组合依赖和启动 ASGI
├─ application/
│  ├─ api_gateway.py                         [已开发/已解耦] REST/WS；只依赖Repository/AssetStore端口
│  ├─ conversation_orchestrator.py           [已开发] session/turn 状态与事件序列
│  ├─ turn_pipeline.py                       [已开发/已解耦] async主链；Logger/Metrics经端口注入
│  ├─ runtime_metrics.py                     [已开发] 纯内存、无I/O延迟指标
│  ├─ interruption_controller.py             [已开发] generation/cancel/queue purge
│  ├─ prompt_compiler.py                     [保留]
│  ├─ output_sanitizer.py                    [保留]
│  ├─ memory_service.py                      [已开发]
│  ├─ retention_service.py                   [已开发]
│  ├─ health_aggregator.py                   [已开发] 真实探针与资源
│  └─ model_registry.py                      [已开发] 清单不是 ready 证据
├─ domain/
│  ├─ conversation.py                        [保留] Session/Turn/状态规则
│  ├─ profile.py                             [保留]
│  ├─ memory.py                              [保留/扩展]
│  └─ cancellation.py                        [已开发] CancellationToken
├─ ports/
│  ├─ asr.py / llm.py / tts.py / avatar.py  [保留/补取消合同]
│  ├─ embedding.py                           [保留]
│  ├─ repositories.py                        [已开发] 应用仓储与审计查询合同
│  ├─ assets.py                              [已开发] 私有资产存储合同
│  └─ observability.py                       [已开发] 日志与运行指标合同
├─ adapters/
│  ├─ silero_vad_adapter.py                  [已开发]
│  ├─ faster_whisper_adapter.py              [已开发]
│  ├─ llama_cpp_adapter.py                   [已开发]
│  ├─ qwen_tts_adapter.py                    [已开发/显式受保护回退]
│  ├─ cosyvoice_tts_adapter.py               [已开发/V1默认非TensorRT]
│  ├─ live_talking_adapter.py                [已开发/已验收恢复]
│  └─ bge_embedding_adapter.py               [已开发]
└─ infrastructure/
   ├─ sqlite_repository.py                   [已开发]
   ├─ vector_index.py                        [已开发] V1 禁止内存 fallback 冒充 ready
   ├─ asset_store.py                         [已开发]
   └─ structured_logger.py                   [已开发/经Port注入]

workers/speech_worker/
├─ server.py                                 [已开发] :8091
└─ scheduler.py                              [已开发] GPU admission / bounded queue

workers/avatar/                              [上游]
scripts/windows/RuntimeLauncher.ps1          [已开发] 生命周期与功能探针
tests/{b3,b4,b5}/                            [已开发] 目标机验收runner
```

目标依赖只允许 `api → application → domain + ports`；`adapters/infrastructure → ports/domain`。ARCH1已把`SqliteRepository`、`AssetStore`、`StructuredLogger`的具体装配集中到`api/server.py`，运行指标为应用层无I/O实现，并以AST门禁持续保证`application/domain/ports`对`infrastructure/adapters/api`的反向导入为0。

## 4. 实时 TurnPipeline

### 4.1 正常主链

1. Gateway 验证 session 和帧合同，把 20ms PCM 放入该 session 的有界输入队列。
2. VAD 产生 speech_started/speech_ended；ASR partial 只发 UI，final 才创建 turn。
3. PromptCompiler 在 4096 token 预算内拼接人设、最近摘要和长期记忆。
4. LLM token 经 OutputSanitizer 增量清理和语义切句；首个可播分句立即交给 TTS。
5. TTS 音频 chunk 同时送浏览器播放与 Avatar；播放时间戳是口型唯一主时钟。
6. turn 完成后按 recording policy 持久化；候选记忆异步处理，不阻塞下一轮监听。

### 4.2 并发与背压

- 每个 session 最多一个 active turn；每个阶段只有有界 queue。
- GPU 阻塞调用放入受控 worker/thread/process，不占用 ASGI event loop。
- TTS/Avatar 处理不过来时先暂停上游分句，再丢弃迟到视频帧；不得无限缓存音频。
- 每个 queue 暴露 depth/high-water/dropped 指标；会话结束或取消后必须回落到 0。

### 4.3 Deadline

实现继续采用 `implementation-contracts.md §27` 的集中数值。deadline 超时必须产生结构化错误和确定性降级，不能静默继续：ASR/LLM 失败结束语音轮；TTS 失败保留文字；Avatar 失败保留语音和静态肖像。

## 5. 打断与取消不变量

`CancellationToken = {session_id, turn_id, generation, cancelled_at_monotonic_ns, cancelled_at_wall_utc}`。新 turn 或有效 barge-in 会递增 generation 并取消旧 token；延迟只比较关联后的单调时钟，UTC仅用于审计排序。

必须同时满足：

1. LLM 停止读取/转发旧 token；
2. TTS 不再提交旧分句，已生成 chunk 被丢弃；
3. 浏览器播放缓冲收到 purge 命令；
4. Avatar 音频与帧队列清空，迟到帧按 generation 丢弃；
5. 旧 turn 不得写 transcript completion、summary 或 memory candidate；
6. cancel 可以重复执行，不抛未处理异常；
7. 从 VAD 命中到可听静音 P95≤400ms。

所有产生 chunk 或副作用的边界在执行前检查 token，而不是只在流水线入口检查。

### 5.1 WebSocket 全双工实施边界

Gateway 已由 `SessionRuntime` 实现持续 receiver、单 active-turn task、有界 outbound queue 和串行 sender；`InterruptionController` 与 generation fence 已投入真实打断验收。receiver 只解析、校验和入队，不等待模型，多个协程不直接并发调用 `ws.send_json`。

浏览器先建立 `generation → Set<AudioBufferSourceNode>` 注册表与幂等停止合同，再启用全双工 feature flag；播放取消只停止旧 generation 的 source，不得关闭共享 AudioContext 或麦克风采集。旧半双工合同在切换前后都要回归。若单 WS 方案在真实 Chrome 仍出现接收饥饿，才触发“独立控制 WS”备选 ADR；不得由实现者自行扩展协议。

## 6. API 与事件合同

### 6.1 必要 REST

| 方法 | 路径 | 责任 |
|---|---|---|
| POST | `/api/v1/sessions` | 新建 session 与 recording policy |
| DELETE | `/api/v1/sessions/{id}` | 取消 active turn、结束并按策略持久化 |
| PATCH | `/api/v1/sessions/{id}/no_record` | 对整场会话生效，不允许仅影响后续 turn |
| GET | `/api/v1/health` | 聚合真实功能探针与资源 |
| POST | `/api/v1/health/{component}/retry` | 重启/重载单组件并重新探针 |
| GET/PATCH/DELETE | `/api/v1/memories/{id}` | 查询、编辑、原子删除 |
| DELETE | `/api/v1/memories` | 二次确认后全清 |
| POST | `/api/v1/retention/run` | 手动触发可审计清理 |

既有 onboarding/profile/asset 端点继续保留，字段以 schema 为准。

### 6.2 WebSocket

JSON envelope 固定包含 `type/session_id/turn_id/event_seq/occurred_at/payload`。二进制消息只能是协商后的 PCM 帧；超限或非法格式直接关闭该 session 输入，不解析为文本。

最小事件集：

- `session.state.changed`
- `input.level`、`asr.partial`、`asr.final`
- `reply.text.delta`、`reply.text.final`
- `reply.audio.chunk` 或媒体引用
- `barge_in.detected`、`turn.cancelled`
- `component.degraded`、`component.recovered`
- `error`

客户端按 `event_seq` 丢弃重复/倒序事件；服务端仍承担旧 generation 不产生副作用的责任。

## 7. 数据与隐私事务

- `no_record` 在 session 创建后可切换，但一旦启用，对该 session 已产生的 transcript/summary/candidate 做补偿删除，之后所有持久化入口 fail closed。
- 单条记忆删除和全清必须在一个 SQLite 事务中覆盖 memory source、FTS、vector 与派生缓存；审计只保存动作/ID hash/结果，不保存正文。
- `VectorIndex` 的内存 fallback 只允许测试；V1 运行时加载 sqlite-vec 失败时标记 embedding degraded，不得把内存结果当持久化成功。
- 原始麦克风音频只存在内存缓冲；不得进入 tempfile、日志、crash bundle 或测试录像的音轨，除非人工验收明确使用授权 fixture。
- 会话文本 `expires_at = ended_at + 30 days`；RetentionService 使用可注入 UTC clock，启动补偿和重试幂等。
- 创建即 `no_record` 的 session 使用 `2**62` 起始的进程内十进制 ID，不创建数据库 session；会话中开启时先取消待写任务，再事务删除整场业务记录并继续使用同一内存 ID。该策略单向生效。
- no-record 内存 ID 只存在于 Orchestrator 内部，不进入 WS/REST envelope、日志、审计、错误码或浏览器；B4 以 WAL、audit 与 loopback 抓包复核。
- `MemoryRepository` 独占事务边界；`VectorIndex` 不得自行 commit。全清请求必须包含 `{"confirmation":"PURGE_ALL"}`。
- B4 入口为 B3 PASS；最终记忆验收只接受 B3 已 `e2e_accepted` 的真实会话。

## 8. 健康、启动与恢复

### 8.1 ready 定义

| 组件 | 功能探针 |
|---|---|
| Gateway | schema/DB 写读/WS loopback |
| LLM | 加载目标 revision 并返回至少 1 个 token |
| Speech | VAD 静音不误触发、ASR fixture 有 final、TTS fixture 有可解码音频 |
| Avatar | 创建临时 session、接收短音频并产生连续帧/FPS |
| Embedding | 512 维向量 + SQLite vector insert/search/delete |

PID、端口监听或模型文件存在都不能单独构成 ready。

### 8.2 Launcher 责任

- preflight：配置、模型哈希、磁盘、GPU、端口所有权、WSL 可达性；
- start：按依赖启动并等待真实 probe，失败只回滚本次创建的 PID；
- status：机器可读 JSON，区分 stopped/loading/ready/degraded/error；
- recover：只重启失败组件，并验证依赖者重新连接；
- stop：先拒绝新 session，再取消 active turn，flush 允许的数据，最后从上游到下游停止；
- 所有操作幂等，不得按端口强杀不属于本项目的进程。

## 9. 资源与性能策略

- VRAM≤22GB、项目private bytes+RSS≤14GB；在约16GB可用预算内宿主/WSL均保留≥2GB。
- SpeechRuntime 只允许一个 GPU TTS 生成任务并设置队列上限；ASR 与 TTS 组合驻留在目标机实测后固定 profile。
- ADR-008 已将非 TensorRT CosyVoice2 切为默认；V1RC1当前候选以Windows Chrome普通链30/30得到P50/P95=4.102/4.708秒。适配器复位冻结上游跨请求增长的流式hop窗口，并以系统余量3GiB/Gateway RSS4GiB双门回收arena；Qwen仅作为显式回退保留，不与Cosy双常驻。
- 首响定义为 `asr.final occurred_at` 到浏览器实际播放首个非静音样本，不用服务端“生成完成”替代。
- Avatar FPS 同时记录模型推理 `inferfps` 和浏览器实际渲染 `finalfps`。

## 10. 可观测性

每轮必须记录脱敏的：`trace_id/session_hash/turn_id/generation/state/from/to/duration_ms/queue_depth/component/error_code`。性能证据从事件自动生成 CSV，避免人工抄数。

禁止日志字段：原始音频、完整逐字稿、完整 prompt、人设全文、声音/肖像绝对路径、未经 hash 的用户标识。日志轮转和验收录像必须纳入磁盘预算。

## 11. 测试分层

- Unit：状态、不变量、取消幂等、清洗、保留、事务规则。
- Contract：REST/WS schema、adapter stream/cancel/error/health。
- Integration：真实 SQLite/sqlite-vec、真实模型、Windows↔WSL、Avatar session。
- E2E：20 轮、30 打断、降级恢复、记忆/不记录、一键生命周期。
- Performance：首响、静音、FPS、VRAM/RAM、queue/task 趋势、1h soak。
- Privacy：loopback、出站白盒、运行期连接、原始音频、日志与 Git 扫描；物理断网按用户决议不执行且不得冒充已执行。

Mock 测试只能让实体进入“合同通过”，不能进入“已验收”。

## 12. 关键取舍与风险

| 选择 | 得到 | 放弃/风险 | 控制 |
|---|---|---|---|
| 模块化单体 | 简单一致性和调试 | Gateway 故障影响面大 | 降级、supervision、restart |
| 本机进程拆分 | 隔离 GPU/许可证/运行时 | 跨 Windows/WSL 网络复杂 | Launcher 解析与功能探针 |
| asyncio 有界队列 | 低延迟、易取消 | 需严格避免阻塞 event loop | worker + queue metrics |
| SQLite | 原子删除、零运维 | 单写者与扩展加载风险 | 短事务、WAL、启动验证 |
| Cosy默认、Qwen显式回退 | Cosy已通过7秒全链门与授权盲听 | 需保持回退可用 | 单TTS常驻、版本化profile、B5组合复测 |
| Avatar防腐层 + H.264 WS | 隔离上游变化并绕开WSL ICE | 依赖WebCodecs；宿主内存余量窄 | contract、pinned revision、队列≤2、B5长稳态 |

## 13. 架构出门条件

架构实现完成并不等于 V1 出门。只有 [`acceptance-plan.md`](../acceptance-plan.md) AC-01～AC-14 与 AC-04A 全部通过、开放 P0/P1=0，且 B0～B5 与 B2.5 证据完整，才允许标记 V1 Go。ARCH1和RES1已关闭分层/资源红项；完整现场门与INST1-AC07单机隔离可移植性仍须绑定当前revision。INST1-AC06独立机复现为增强保证，不再是V1最低门。

## 14. B2.5 优化扩展

B2.5 不改变本架构的依赖方向。新增 `WarmResponsePolicy`、`WarmResponseCache`、`RuntimeMetrics` 和可选引擎 adapter；`TurnPipeline` 只调用端口，不感知 TensorRT/vLLM 具体实现。普通、严格命中、打断及回退数据流、版本键、资源调度和 ADR 见 [`b25-optimization.md`](b25-optimization.md)。

当前执行顺序是 `B2.5首响/缓存 → B2 Avatar恢复 → B3打断 → B4记忆/隐私 → B5完整组合回归`。证据归属见ADR-009；若任一阶段无法在既有NFR与体验冻结条件内出门，不降低硬门，必须停线并提交备选路线。

## 15. B3～B5 交付扩展

- B3（已实现）：Gateway 已切换全双工 session runtime，并通过统一取消与 generation fence 验收。
- B4（已实现）：记忆、隐私、保留和 sqlite-vec 真实往返已落地；运行时不以 FTS-only 或内存 fallback 冒充 ready。
- B5（已实现、外部门待闭环）：授权撤销、资产版本、默认入口、组合回归和目标机生命周期均已执行；口型量化、分层和资源红项已关闭，人工Narrator/物理麦克风与AC07当前revision报告仍需补证。
- 详细计划和真实门槛见 `stages/B3～B5`；可编辑总图为 `cyberWife-b3-b5-delivery-gap.drawio`。
