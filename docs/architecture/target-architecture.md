# cyberWife V1 基线与 V2 演进目标架构

**版本**：3.3
**日期**：2026-10-07
**状态**：V1目标架构已实现；单场景同一人物Idle/实时口型原子切换、AC-06A与项目所有者人工总验收均PASS，高清与口型自然度升级进入V2-X8
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
| 前端 | ConversationClient/MediaSession保持主链；UX13～15实现intro→idle→同场景实时Avatar→outro、常驻Idle双缓冲与Canvas延迟清理 | 同一时刻只显示一个人物表面；视觉序列不得接管实时音频/口型时钟；失败回退Idle/静态图 | 单表面与无闪动自动门PASS；多实体V2待开发 |
| API | 二进制音频、真实事件链、session/memory/health/asset/profile API均已实现；具体仓储、资产存储和日志只在组合根注入 | 保持合同稳定与单向依赖 | 已开发/ARCH1验收通过 |
| 会话领域 | Session/Turn 六态、event_seq、持久化和迟到判断已实现 | 领域状态不持有 GPU task | 已开发/已验收 |
| 实时编排 | 异步TurnPipeline、分句、媒体流水线、统一取消与generation清理已实现 | 保持有界队列和取消合同 | 已开发/已验收 |
| VAD/ASR | SpeechRuntime真实进程与20轮final合同通过；UX8统一繁简/普通话词形与segment展示 | Chrome 900ms句中停顿端点，保持20ms流式输入与不落盘 | 已开发；机器与项目所有者人工验收PASS |
| LLM | Windows llama.cpp真实stream、低风险profile与跨阶段取消已通过 | 不迁移高成本runtime | 已开发/已验收 |
| TTS | Cosy默认链30/30、普通链P95≤7秒、授权盲听5/5；统一取消已接入 | Qwen保留显式回退 | 已开发/已验收 |
| Avatar | H.264/WebCodecs传输、打断清队列、降级/恢复与长稳态通过；20ms实时PCM使用50ms调度抖动容忍与260ms活跃批窗口，避免Mel批次误插静音 | AC-06A机器嘴部响应4/4及浏览器人工体验通过；进一步高清与自然度进入V2-X8 | V1 PASS；V2质量优化待开发 |
| 人物生成 | 身份参考+完整场景关键帧→Wan首尾条件→人工确认；UX14保留768×432完整Idle帧构建`scenev1`说话Avatar，不抠图、不叠第二人物 | intro/idle/live/outro共享批准清单；逐素材人工身份、场景和嘴部自然度签署 | `scenev1`已active；同场景实时嘴部机器PASS |
| 数据 | SQLite/FTS/sqlite-vec、Memory/Retention、手工新增、候选确认/拒绝、原子删除与no-record均已实现 | 候选确认前不召回；保持事务与保留策略 | 已开发/真实语音链验收 |
| 健康 | 六组件真实probe、资源、engine、缓存与首响分段状态已实现 | 保持真实状态，不以文件存在冒充ready | 已开发/已验收 |
| 启动 | audit/prepare/verify与start/status/recover/stop已实现；AC06R以本地制品清单生成本机模型注册表、私有参考音频/Avatar/Cosy源码，Gateway和Launcher不再依赖开发机硬编码素材；双身份拒绝和五项空状态约束新环境 | 在真实新Windows用户+干净WSL运行已完成的执行器 | 当前机迁移/真实启停PASS；外部环境待验 |
| 验收 | V1FINAL报告绑定Git revision；AC09总门复算完整源码、依赖、前端和证据SHA，并校验人工/部署报告同提交；部署策略显式区分AC07同机隔离与AC06独立机 | 保持失败关闭与脱敏归并 | 项目所有者人工、发布冻结、AC07与最终聚合均PASS |

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
│  ├─ memory_service.py                      [已开发/UX10] 手工记忆、候选确认/拒绝、召回隔离
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
tests/ux10/                                  [已开发] 真实语音候选记忆验收
ops/avatar_idle_pipeline.py                  [已开发/UX11回退] 旧完整帧Idle与派生调度
ops/offline_scene_compositor.py              [已开发/兼容回退] Alpha预合成，不再是目标路线
ops/fullscene_idle_pipeline.py               [已开发/UX12候选] 完整场景三姿势、Wan首尾条件、10秒全帧闭环与门禁
ops/comfy_avatar_fullscene_idle_api.json     [已开发/UX12候选] 本机Wan完整场景API工作流
ops/scene_sequence_pipeline.py               [已开发/UX13] 开场、严格正脸Idle、反向结束与自动指标
ops/install_scene_sequence.py                [已开发/UX13] 人工批准令牌、哈希校验和版本化私有安装
backend/cyberwife/application/avatar_asset_service.py [已开发/UX13] 序列清单验证和私有媒体路径门
prototype/src/App.tsx                        [已开发/UX13] 宽高比舞台、记忆工作台与intro/idle/live/outro状态机
ops/build_video_avatar.py                     [已开发/UX14] 保留完整场景帧构建scenev1说话Avatar
prototype/src/styles.css                      [已开发/UX14] live首帧原子替换Idle、单人物全舞台表面
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

架构实现完成并不等于 V1 出门。只有 [`acceptance-plan.md`](../acceptance-plan.md) AC-01～AC-14、AC-04A 与 AC-06A 全部通过、开放 P0/P1=0，且 B0～B5 与 B2.5 证据完整，才允许标记 V1 Go。ARCH1、RES1、实时口型AC-06A、项目所有者人工总验收、INST1-AC07与最终聚合均已关闭对应红项，V1正式完成。INST1-AC06独立机复现为增强保证，不是V1最低门。

## 14. B2.5 优化扩展

B2.5 不改变本架构的依赖方向。新增 `WarmResponsePolicy`、`WarmResponseCache`、`RuntimeMetrics` 和可选引擎 adapter；`TurnPipeline` 只调用端口，不感知 TensorRT/vLLM 具体实现。普通、严格命中、打断及回退数据流、版本键、资源调度和 ADR 见 [`b25-optimization.md`](b25-optimization.md)。

当前执行顺序是 `B2.5首响/缓存 → B2 Avatar恢复 → B3打断 → B4记忆/隐私 → B5完整组合回归`。证据归属见ADR-009；若任一阶段无法在既有NFR与体验冻结条件内出门，不降低硬门，必须停线并提交备选路线。

## 15. B3～B5 交付扩展

- B3（已实现）：Gateway 已切换全双工 session runtime，并通过统一取消与 generation fence 验收。
- B4（已实现）：记忆、隐私、保留和 sqlite-vec 真实往返已落地；运行时不以 FTS-only 或内存 fallback 冒充 ready。
- B5（已实现并验收）：授权撤销、资产版本、默认入口、组合回归和目标机生命周期均已执行；分层、资源、AC07、实时口型与项目所有者人工总验收均通过。
- 详细计划和真实门槛见 `stages/B3～B5`；可编辑总图为 `cyberWife-b3-b5-delivery-gap.drawio`。

## 16. V2 演进边界

V2采用ADR-013的“先体验、后扩容”，详细任务和验收只在 [`../V2-development-plan.md`](../V2-development-plan.md) 维护。本节冻结架构方向。

### 16.1 V2-X：兼容层内的体验优化

- 保留现有单一活动 Avatar 合同和 `TurnPipeline`，不在体验阶段引入多角色并发。
- 多源照片、Appearance和Scene以版本化manifest保存；创建时即使用不可变UUID、SHA-256、授权ID和provenance。
- 原图只读、派生资产分离；用户未确认的图像描述不得进入Profile/Memory。
- 记忆图谱先作为内置SQLite记忆的只读派生视图；任何边必须能回到源记忆或用户确认事件。
- 生成模型与实时模型串行调度，不双常驻；V1的RAM、VRAM、首响、打断和稳定性门保持不变。

#### 16.1.1 D1锁定的运行实体

```text
React AppShell（复用）
  ├─ DevicePanel → InputAudioSessionController（修改：校准/device/PTT）
  ├─ OutputControls → MediaSession（修改：gain/compressor/内存重播）
  ├─ SourcePackPanel / StageControls（新增）
  ├─ MemoryWorkbench（从Settings拆分）
  └─ ConversationScreen
       ├─ SessionLifecycleController（新增：visibility/network/health generation）
       ├─ StagePresentationController（新增：单表面状态机）
       └─ AvatarSessionController（修改：帧年龄/漂移/质量档）
                 │ REST + 既有6字段WS envelope
                 ▼
Gateway api/server.py（修改，仅校验/路由）
  ├─ 既有 TurnPipeline / SessionRuntime / MemoryService
  ├─ ExperienceSettingsService / QualityGovernor / VoiceStylePolicy（新增）
  ├─ SourcePackService / ScenePresetService / VisualClaimService（新增）
  └─ MemoryGraphService（新增、只读派生）
          │ ports
          ├─ JsonManifestRepository（新增，原子revision）
          ├─ SqliteMemoryRepository（修改，派生边删除传播）
          └─ VisualDescriptionPort（新增，本地实现）
```

依赖仍为`UI/API → application → domain + ports ← infrastructure/adapters`。`App.tsx`只做组合，不允许新增manifest、质量分级或确认策略。完整文件、API、状态机和schema以[`../stages/V2-X-D1/implementation-contracts.md`](../stages/V2-X-D1/implementation-contracts.md)为唯一实现合同。

#### 16.1.2 权威数据与一致性

- V1的`asset_versions/active_assets/avatar_derivatives`在X0～X1迁移期间保持活动事实源；V2-X manifest通过旧asset id建立一次性、幂等映射，完成相应子阶段验收后才成为舞台选择事实源。
- 原图与派生媒体在私有资产根分开存放；manifest采用同目录临时文件、fsync和原子替换，`revision`CAS失败时不改变active。
- SQLite `memories`继续是长期记忆权威。聚类、节点和边均为可重建派生索引，必须携带`source_memory_ids`并和源删除同事务传播。
- `VisualClaim`只有`confirmed`状态可供`PromptCompiler`读取；候选或模型推断不得写Profile/Memory。

#### 16.1.3 实时控制与降级

- `SessionLifecycleController`和现有conversation generation分别管理页面资源代际和对话轮代际；任何异步回调必须同时通过相关代际检查。
- 音频是质量降级的主时钟。`QualityGovernor`可丢弃过期视频帧、降低视频档或回退Idle/静态图，但不得暂停/拉伸音频追帧。
- `StagePresentationController`执行`intro→idle→listening/thinking/pre-speech→live→recovery→idle→outro`，任一时刻只有一个可见人物表面；`prefers-reduced-motion`直接回退低幅Idle或静态图。
- X0.1～X9每项使用独立`v2x.*` flag；关闭单项只恢复对应V1行为，不删除用户素材或重写稳定ID。

#### 16.1.4 资源与部署不变量

- 浏览器、WSL2 Gateway/Speech/Avatar和Windows LLM拓扑不变；PWA是浏览器渐进增强，不引入Electron/Tauri前置条件。
- Service Worker只允许缓存带内容哈希的前端静态壳，`/api/`、`/ws/`、私有媒体和用户数据统一network-only/no-store。
- 重型素材/视频生成开始前必须停止实时模型并确认资源余量；生成结束释放显存后才允许恢复对话。项目不可回收RAM峰值≤14GB、VRAM≤22GB、宿主/WSL余量≥2GB。

### 16.2 V2-A：正式领域扩容

```text
Browser UI
  ├─ Character / Appearance / Space 管理
  └─ Memory Workbench / Connector Control
        │ REST + WS
        ▼
App Gateway（模块化单体）
  ├─ Conversation Context（复用V1）
  ├─ Character Context      [新增]
  ├─ Space Context          [新增]
  ├─ Asset Package Context  [新增]
  └─ Memory Platform        [扩展]
       ├─ Built-in SQLite Provider（权威写存储）
       ├─ RAG / llmwiki Adapter
       ├─ MCP Tool Bridge
       └─ Codex / Claude CLI Bridge
                            │
                            └─ 低权限Plugin Host（仅不可信执行）
```

关键实体为`Character`、`AppearanceSet`、`SourcePack`、`Rendition`、`Space`、`ActiveContext`、`MemoryEdge`、`MemoryCluster`和`ProviderRegistration`。`ActiveContext`在本地用户范围内仍为单例，但引用的各聚合不再是单例。切换必须在事务内检查授权、就绪状态和资源预算，失败保持旧上下文。

依赖方向继续是`api → application → domain + ports`；连接器和插件只能实现port，禁止application/domain直接依赖MCP SDK、CLI实现、llmwiki或外部RAG客户端。V2不拆业务微服务，只有不可信插件宿主可以进程隔离。

### 16.3 数据与迁移

- V2-X manifest先登记为V2-A正式实体，ID保持不变；禁止重新生成ID造成资产失联。
- 私有路径按`characters/<id>`、`spaces/<id>`、`renditions/<id>`隔离，所有路径由服务端验证过的ID解析。
- 导入只进入staging；schema、哈希、授权、配额和路径穿越检查全过后原子提升。
- 内置SQLite仍是核心记忆权威写存储；外部提供方默认只读/候选，需统一策略和用户确认才能固化。
- schema与资产迁移必须有前置备份、dry-run、重复执行和回滚证据。

### 16.4 阶段出门

V2-X必须先通过V2X-AC01～08，V2-A才可开发；其中AC07只能在X8完成后签署最终组合回归。V2-A通过V2A-AC01～07后才可以宣称支持多形象、多空间、导入导出或可插拔记忆。任何人物/声音/记忆串用、未授权事实固化、插件越权或V1性能回退均为P0/P1停线项。
