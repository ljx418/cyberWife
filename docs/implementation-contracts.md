# cyberWife V1 实施合同补遗

**版本**：2.1　**日期**：2026-09-25　**状态**：§31～§36 为当前后端重基线；旧 M0～M6 叙述仅保留历史上下文  
**作用**：承载目标架构、模型清单、原型规格与追踪矩阵中未唯一化的实施合同。当前开发批次使用 B0～B5；所有数值为 V1 实施合同，如需变更须同步更新本文件、PRD、目标架构、追踪矩阵与 Draw.io。

本文件覆盖的待审项：
- I-01 目录骨架缺 `workers/avatar/` 与 `model-registry.local.yaml` 路径
- I-06 数据表缺 `session_transcripts/session_summaries`、`memory_vectors` 维度未固化、`audit_events` 缺取证字段
- I-11 ASR/TTS 分时峰值与约16GB可用 RAM 预算已在 §5 和 V1.3 内存变更中固定
- A7 bge-small-zh-v1.5 维度未固化
- A8 Prompt 注入预算未定
- A10 浏览器 20ms 帧实现方式未定
- A11 Avatar本机媒体边界缺失（原WebRTC方案已由ADR-010取代）
- R-01 模型 fallback 与离线镜像策略缺失
- R-04 WSL→Windows 跨边界解析机制
- R-06 audit_events 哈希算法与取证字段
- R-11 Wav2Lip LICENSE 引用与触发条件
- R-15 Draw.io p6 r3 license review 子项

---

## 1. 目录骨架唯一性（修补 I-01）

`target-architecture.md §3` 目录树新增与明示：

```text
backend/
└─ cyberwife/
   ├─ api/ApiGateway.py
   ├─ application/
   ├─ domain/
   ├─ ports/
   ├─ adapters/
   └─ infrastructure/
       ├─ SqliteRepository.py
       ├─ VectorIndex.py
       ├─ AssetStore.py
       ├─ ModelRegistry.py
       └─ StructuredLogger.py

workers/
├─ speech_worker/
│  ├─ server.py                 [VAD/ASR/TTS GPU worker :8091]
│  └─ scheduler.py              [GPU admission/backpressure]
└─ avatar/
   ├─ server.py                 [LiveTalking/Wav2Lip256 :8010]
   └─ webrtc_host.py             [host candidates only, no STUN]

ops/
└─ windows/
   ├─ RuntimeLauncher.ps1       [start/stop/status/recover]
   ├─ StartLlamaCpp.ps1         [Windows llama-server :8090 wrapper + health probe]
   └─ ResolveWindowsHost.ps1    [解析 %WINDOWS_HOST% 并探测 :8090]

config/
├─ default.example.toml         [无秘密]
├─ model-registry.example.yaml  [仓库内示例，去绝对路径]
└─ model-registry.local.yaml    [本机私有，绝对路径，Git ignore]

schemas/                        [JSON Schema 合同基线，M1-02 起填充]
├─ rest/
│  ├─ health.schema.json
│  ├─ profile.schema.json
│  ├─ onboarding_draft.schema.json
│  ├─ consent.schema.json
│  ├─ asset.schema.json
│  ├─ session.schema.json
│  ├─ memory.schema.json
│  ├─ audit.schema.json
│  ├─ retention.schema.json
│  └─ error_envelope.schema.json         [统一错误响应 5 字段]
├─ ws/
│  ├─ envelope.schema.json               [公共 6 字段 envelope]
│  ├─ state.changed.schema.json
│  ├─ transcript.schema.json
│  ├─ reply.schema.json
│  ├─ barge_in.schema.json
│  ├─ turn.cancelled.schema.json
│  ├─ component.schema.json
│  └─ error.schema.json
└─ events/
   └─ domain_events.schema.json          [14 领域事件 payload]

migrations/
└─ 0001_init.sql                [初始 schema + memory_vectors(vec_f32(512)) + session_transcripts/session_summaries + onboarding_drafts + profile_history]

tests/
├─ unit/                        [pytest]
├─ contract/                    [REST/WS schema + 5 adapter]
├─ integration/                 [DB tx / functional probe / Win↔WSL]
├─ e2e/                         [Playwright]
├─ performance/                 [固定语料+温箱基线 CSV]
└─ privacy/                     [端口/外联/音频扫描/Git scan]
```

prototype/src/ 现有文件：`App.tsx`、`styles.css`、`types.ts`、其他 `tests/`、`index.html`、`package.json`、`tsconfig.json`、`vite.config.ts`、`playwright.config.ts`。V1 阶段在 `prototype/src/` 下增 `app/AppShell.tsx`、`features/onboarding/OnboardingFlow.tsx`、`features/conversation/ConversationScreen.tsx`、`features/settings/SettingsDrawer.tsx`、`services/ConversationClient.ts`、`services/MediaSession.ts`、`platform/HostBridge.ts`（共 7 个目标文件，含 HostBridge；保留契约 `App` 的现有视觉不破坏）。

---

## 2. 数据表补全（修补 I-06、A7）

`target-architecture.md §7` 表补全：

```sql
-- 已在 §7 列出的表保持原样

-- 修补 1：memory_vectors 维度固化
CREATE TABLE memory_vectors (
  memory_id INTEGER PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
  embedding vec_f32(512),                      -- BAAI/bge-small-zh-v1.5 输出维度
  model_id   TEXT NOT NULL DEFAULT 'bge-small-zh-v1.5',
  revision   TEXT NOT NULL,
  created_at TEXT NOT NULL
);

-- 修补 2：缺 transcript/summary 表
CREATE TABLE session_transcripts (
  session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  full_text  TEXT NOT NULL,
  sha256     TEXT NOT NULL,                    -- 校验分块仅出现在加密摘要中
  updated_at TEXT NOT NULL
);
CREATE TABLE session_summaries (
  session_id INTEGER PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
  summary    TEXT NOT NULL,
  token_est  INTEGER NOT NULL,
  updated_at TEXT NOT NULL
);

-- 修补 3：audit_events 增补取证字段（修补 R-06）
CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY,
  action TEXT NOT NULL,                        -- 取值见 §3
  entity_type TEXT NOT NULL,                   -- consent|profile|asset|memory|session|health
  entity_id_hash TEXT NOT NULL,                -- SHA256(entity_id || session_salt)[:16] hex
  result TEXT NOT NULL,                        -- success|failure|rollback
  -- 取证字段（修补 R-06）：
  deleted_row_count INTEGER,                   -- 实际删除源记录条数
  fts_count_before INTEGER,
  fts_count_after  INTEGER,
  vector_count_before INTEGER,
  vector_count_after  INTEGER,
  error_code TEXT,                             -- 失败时记录
  trace_id TEXT,
  created_at TEXT NOT NULL
);

-- 修补 4：sessions.expires_at 基准明确（修补 I-12）
-- expires_at = ended_at + 30d（自然日，UTC）；started_at 仅用于审计展示
-- MemoryRecord 没有 expires_at，长期记忆由用户手动删除触发
```

---

## 3. audit_events.action 取值（修补 I-06）

| action 取值 | 触发场景 | 关联 FR |
|---|---|---|
| `consent.granted` | 用户首次勾选授权 | FR-02 |
| `consent.revoked` | 用户撤销授权 | FR-02 |
| `asset.uploaded` | 资产上传并 magic bytes 通过 | FR-04/05 |
| `asset.previewed` | 资产预览创建 | FR-04/05 |
| `asset.activated` | active version 切换 | FR-04/05 |
| `asset.rollback` | 上一版本恢复 | FR-04/05 |
| `profile.updated` | Profile 保存 | FR-06 |
| `memory.committed` | 候选记忆固化 | FR-12 |
| `memory.updated` | 记忆编辑（重建 FTS+向量） | FR-12 |
| `memory.deleted` | 单条删除 | FR-12 |
| `memory.purge_all` | 全清（带二次确认 token） | FR-12 |
| `session.created` | POST /sessions | FR-08 |
| `session.ended` | DELETE /sessions/{id} | FR-08 |
| `session.no_record` | 本次不记录启用 | FR-13 |
| `retention.expired` | 30 天清理执行 | FR-14 |
| `retention.failed` | 清理失败回滚 | FR-14 |
| `health.degraded` | 组件降级 | FR-15 |
| `health.recovered` | 组件恢复 | FR-15 |

---

## 4. 哈希与 ID 算法（修补 R-06、A13）

| 字段 | 算法 |
|---|---|
| `entity_id_hash` | `SHA256(entity_id \|\| session_salt)[:16]` 十六进制 lower case；`session_salt` 由启动时生成，存 `config/.salt`（仅本机） |
| `session_id_hash` | `SHA256(session_id \|\| session_salt)[:16]` |
| `trace_id` | ULID（26 字符，Crockford base32），按时间排序 |
| `turn_id` | 单调递增 64-bit 整数，per session 严格递增 |
| `event_seq` | 单调递增 64-bit 整数，per session 严格递增 |

敏感字段黑名单（禁止写入日志与审计正文字段）：
- 原始音频字节 / 编码路径 / 临时文件名
- 完整转录、完整 prompt、完整 LLM 响应
- 声纹嵌入向量
- 资产绝对路径、文件名原始字符串
- 真实姓名、住址、证件号（即便用户提供也禁止记录）

---

## 5. 资源预算数字（修补 I-11 + V1.3 测量纠正）

### 5.1 VRAM 瞬时峰值（24GB 总，≤22GB 出门）

**测量纠正（2026-09-24）**：
- `nvidia-smi` 读数含 **~5GB CUDA driver context overhead**（即使无进程使用 GPU 也会显示该占用），这部分**不算模型真实占用**
- `torch.cuda.mem_get_info` 读数才是**当前进程实际活跃张量 + cached pool**
- V1.2 红线撤销后**任何显存测量需用 torch 读数**，不要用 nvidia-smi 估算真实模型占用

下表数字已**扣除 CUDA context overhead**，按 torch 实测校准：

| 时刻 | LLM | ASR | TTS | Avatar | 合计 | 余量 |
|---|---:|---:|---:|---:|---:|---:|
| 空闲（仅 LLM loaded） | 9 | 0 | 0 | 1.3 | **10.3** | 13.7 |
| 听（VAD+ASR active） | 9 | 3 | 0 | 1.3 | **13.3** | 10.7 |
| 想（LLM streaming） | 9 | 0 | 0 | 1.3 | **10.3** | 13.7 |
| 说（LLM 已停 + TTS active） | 9 | 0 | **5–6** | 1.3 | **15.3–16.3** | 7.7–8.7 |
| ASR↔TTS 切换峰值（≤500ms） | 9 | 3 | **5–6** | 1.3 | **18.3–19.3** | 4.7–5.7 |

**注**：TTS 单组件当前默认 CosyVoice2-0.5B 约 5GB；Qwen3-TTS-12Hz-1.7B-Base 约 6GB（含 speech_tokenizer），仅作为显式回退。§10 fallback chain 中"ASR int8"已默认开启（节省 0.5GB）。

Speech Worker §1 写明 ASR 与 TTS 分时调度（不同时驻留 ≥ 500ms 持续时间）。最坏组合按"ASR↔TTS 切换峰值"18.3–19.3GB，留 4.7–5.7GB 余量；CosyVoice 默认轨相较 Qwen 回退轨保留更多余量。

### 5.2 约16GB可用条件下的14GB项目 RAM预算

| 项目组件 | 峰值上限 |
|---|---:|
| Windows llama-server 工作集（GGUF mmap；不是文件尺寸） | 6.0 GB |
| WSL Gateway + SQLite（cache cap 256MB） | 0.8 GB |
| WSL Speech Worker + 当前阶段 ASR/TTS 二选一 | 3.5 GB |
| WSL Avatar/LiveTalking | 1.5 GB |
| BGE 按需推理（完成后释放） | 0.5 GB |
| Browser（单个验收窗口） | 1.0 GB |
| 项目瞬时缓冲与测量误差 | 0.7 GB |
| **项目可归因峰值硬上限** | **14.0 GB** |

目标机物理内存32GB，启动前约16GB可用；剩余约2GB不是可消费配额。WSL当前15.52GiB上限是合法目标环境，不再要求28GB。14GB主门槛按Windows项目进程private bytes + WSL项目进程RSS计算；同时记录Windowsworking set、宿主`Available MBytes`、WSL `MemAvailable`和swap-in。GGUF mmap/file-backed working set具有共享/可回收语义，单列观察但不与Linux RSS机械相加冒充不可回收峰值。

### 5.3 磁盘 100GB 分项

| 分项 | 预算 | 说明 |
|---|---:|---|
| 依赖环境 | 30 GB | Python env（~8GB，含 torch/ctranslate2/whisper）+ Node modules（~3GB）+ 系统 CUDA/MSVC 运行时 |
| 应用私有资产与数据库 | 25 GB | 照片/声音版本（≤20GB）+ SQLite（含向量）/WAL/备份 |
| 临时缓存 | 20 GB | LLM 推理 KV（动态回收 ≤10GB）+ Avatar 帧缓存（≤4GB）+ 浏览器 IndexedDB（≤2GB）+ ASR 解码（≤2GB） |
| 日志与验收证据 | 10 GB | JSONL 日志（轮转 ≤30 天，≤5GB）+ 截图/视频/CSV（≤5GB） |
| 升级与安全余量 | 15 GB | V1→V2 迁移缓冲、模型补丁 |
| **合计** | **100 GB** |

剩余 < 10GB 时停止新缓存并提示（与 NFR-09 一致）。

---

## 6. Prompt 注入预算（修补 A8）

| 项 | 默认值 | 可调（config/prompt.toml） |
|---|---|---|
| 注入上下文总 token 上限 | 4096 | 2048–8192 |
| Profile/人设 段最大 token | 600 | 200–1000 |
| 短期上下文最近会话摘要条数 | 3 | 1–10 |
| 短期上下文每条摘要最大 token | 300 | 100–600 |
| 长期记忆向量召回 top-k | 4 | 1–10 |
| 长期记忆相似度阈值（cosine） | 0.55 | 0.40–0.80 |
| FTS5 关键词召回 top-k | 6 | 0–20 |
| 记忆预算总 token | 800 | 100–2000 |
| 超出预算截断策略 | 按相似度从低到高丢弃 | — |

LLM 8K context，预留约 1500 token 给输出、500 token 给系统与控制；模型调用总上下文 ≤ 6000 token。

---

## 7. 浏览器 20ms 帧与 WS 帧合同（修补 A10）

### 7.1 采集与分帧

- **采集**：`AudioContext`（`sampleRate=16000`，单声道）→ `AudioWorklet`（`AudioWorkletProcessor` 自定义）→ 20ms PCM 帧（16000 × 0.02 = 320 samples）。
- **编码**：PCM Int16 LE（每帧 640 字节）；同时记录峰值音量（dBFS）作为输入电平事件，与音频帧并行发送。
- **设备事件**：`devicechange` 监听 + `MediaStreamTrack.readyState==='ended'` 检测；设备丢失时本地发 `audio.device_lost` WS 事件并提示用户；重连成功后发 `audio.device_back`。
- **不记录模式**：所有帧仅驻留在 AudioWorklet `port.postMessage` 缓冲，0 落盘；Speech Worker 也仅在内存维护 VAD 窗口。

### 7.2 WS 帧协议

- 二进制帧（`binary_type='arraybuffer'`）承载音频：前 4 字节 `turn_id`（uint32 LE）+ 2 字节 `chunk_seq`（uint16 LE）+ 后续 640 字节 PCM。
- JSON 帧承载控制事件：`audio.device_lost` / `audio.device_back` / `audio.silence` / `audio.level`（每 100ms 一次电平）。
- 帧大小限制：≤ 4KB；服务端关闭连接并返回 `code=frame_size_limit`。

---

## 8. Avatar H.264 WebSocket合同（修补A11，ADR-010）

### 8.1 连接与安全

- 端点：`ws://127.0.0.1:8010/ws/v1/avatar`；服务监听、TCP peer与`Origin`主机均必须为loopback。
- 连接后先发送JSON `video.config`；首个真实解码帧前客户端不得显示ready。
- 视频通道不发送音频；Gateway PCM是浏览器唯一音频与主时钟。

### 8.2 配置与二进制帧

```json
{"type":"video.config","version":2,"session_id":"...","codec":"avc1.42E01F","format":"annexb","fps":25,"queue_limit":2,"audio":"gateway-pcm"}
```

每条二进制消息包含一个Annex-B access unit。version 2 使用18字节小端头：`version:u8`、`flags:u8`（bit0=key）、`width:u16`、`height:u16`、`timestamp_ms:u32`、`sequence:u32`、`generation:u32`，其后为H.264 payload；version 1 的14字节头仅作旧客户端兼容。关键帧必须携带SPS/PPS。编码优先`h264_nvenc`，同进程只允许回退`libx264/ultrafast/zerolatency`。

### 8.3 背压、恢复与FPS

- 每客户端发送队列上限2；满时丢最旧视频帧并增加`late_video_frames_dropped`，不得阻塞PCM。
- 进程内独立控制线程监听`http://127.0.0.1:8011/healthz`；它不得调用模型、渲染队列或持久化，只返回`{"status":"ready","protocol":"avatar-control-v1"}`，绑定失败必须阻断Avatar启动。
- 视频队列连续500ms无帧时，8010 WebSocket发送`{"type":"avatar.heartbeat","version":1,"session_id":"...","monotonic_ms":...}`。合法二进制帧和该心跳均刷新媒体活性，且控制消息不得计入视频FPS。
- 产品`AvatarSession`以WebCodecs低延迟解码到canvas。媒体活性超过1200ms时，以500ms上限探测8011：控制存活则软降级（清canvas、保留WS/decoder/session），控制不可达或WS断线则硬降级并指数退避同页重连；总降级时间必须≤2秒。
- 软降级只允许由后续成功解码的真实帧恢复`ready`；heartbeat不得单独恢复动态图。硬降级后的首个真实解码帧才允许ready并增加连接代次。
- 新WS会话与幸存的对话generation属于不同生命周期：仅在首帧建连期间允许该新会话的generation-0 idle关键帧建立canvas；连接赋值后立即恢复严格generation fence，下一回答由`setGeneration`切至当前代次。不得把旧WS的迟帧用于建连。
- Avatar在某个非零generation建立后，其无音频元数据的idle帧继承最近generation；只有新进程/新session尚未收到真实音频时才输出generation 0。该规则避免同一回答尾部被误判旧帧并在媒体时间轴制造FPS缺口。
- 验收同时要求媒体/服务端finalfps≥25、inferfps≥25、decoder backlog≤3、WebSocket队列丢帧=0；浏览器墙钟值保留诊断并在B5检查长期漂移。
- 目标机Wav2Lip使用`batch_size=4`。浏览器对每个新turn的第一个PCM源预留295ms Avatar lead，后续20ms源继续无缝排程；打断沿用generation栅栏立即取消，不等待预留时间。该值来自UX5同一目标机冷/热四次真实首嘴型帧218.060～370.307ms的中点校准，变更模型、batch或硬件后必须重测，不得照搬。

---

## 9. WSL→Windows 跨边界解析（修补 R-04）

`ops/windows/ResolveWindowsHost.ps1` 启动时执行（幂等）：

1. 通过 `wsl hostname -I` 取 WSL 视角的 Windows 主机 IP（首选）。
2. 备用：`(Get-CimInstance Win32_NetworkAdapterConfiguration | Where {$_.IPEnabled} | Select -First 1).IPAddress`。
3. 把结果写入 `config/runtime.local.toml` 的 `gateway.windows_llama_host` 字段。
4. App Gateway 启动时通过 `/proc/net/route` 解析 WSL 默认网关（避免硬编码），并写入 `wsl.host_map`。
6. 端口可达性：使用 `httpx.AsyncClient(loopback_or_resolved, timeout=2s)` 验证 `:8090 /api/v1/health`。
7. 失败：连续 3 次进入 `error`，RuntimeLauncher 阻断启动。

断网场景下 `wsl hostname -I` 仍可工作（不依赖 DNS），且配置已经写入本地文件，无需重新解析。AC-13 验收时直接复用 runtime.local 配置，不重新探测（避免误判）。

---

## 10. 模型 fallback 与离线镜像策略（修补 R-01）

| 主模型 | fallback（仅模型加载失败时） | 许可证影响 |
|---|---|---|
| Silero VAD v5 | Silero VAD（最新 hub 默认入口 `silero_vad(onnx=False)`，不再有 v5 显式 callable）/ webrtcvad（精度低） | 重新评审（API 变更需重测 §18 barge_in 400ms 门槛） |
| Faster-Whisper large-v3-turbo | 退至 `medium` 或 `small` | 同 MIT 兼容 |
| Qwen3-14B-Instruct Q4_K_M | 退至 Qwen3-8B-Instruct Q4_K_M | 需 M0 重新核验 |
| Qwen3-TTS-12Hz-1.7B-Base | V1 不自动切换 TTS；失败即 `degraded/error` 并阻止发布 | CosyVoice2-0.5B 仅为独立候选，须经 ADR 才可切换 |
| Wav2Lip256 | 静态图降级（不发音频） | 维持非商用 |
| BAAI/bge-small-zh-v1.5 | 退至 bge-base-zh-v1.5（改维度 768） | 同 MIT 兼容；DB 重建 |

离线镜像策略：
- 启动器预检时校验 `~/.cache/huggingface` 已存在目标仓库 `models--*--snapshots/*` 完整快照。
- 缺失时仅警告，不自动下载；如缺主模型，标记 `blocked`，阻断 M1。
- 启动器自带 `--offline-strict` 开关：禁止任何网络下载，缺失即失败。

**真人素材路径（ADR-006 落地，M2-stretch 补强）**：
- 私有资产根：`~/.cyberWife/assets/{portrait,voice}/`（WSL2 ext4；不进 C 盘项目目录、不进 ComfyUI 公共模型库）
- audit 目录：`~/.cyberWife/audit/`
- salt 文件：`~/.cyberWife/audit/.salt`（启动时生成，chmod 600）
- 授权记录：`~/.cyberWife/audit/.consent.json`（Git ignore，仅本机）
- runtime 配置：`config/runtime.local.toml`（Git ignore，仅本机）
- 写真/声纹任何写入路径必须经 `entity_id_hash = SHA256(real_path + salt)[:16]` 派生，**严禁**在代码/日志/审计/测试 fixture 出现字面文件名、人名、字面路径；详见 `docs/human-consent.md`（该文档本身亦被 .gitignore 屏蔽）。

---

## 11. Wav2Lip 许可证引用与触发条件（修补 R-11）

`model-manifest.md §1` Avatar 行填：

```yaml
component: avatar
logical_id: livetalking-wav2lip256
absolute_path: <本机私有>
filename_or_revision: Wav2Lip256 + LiveTalking commit <hash>
size_bytes: 0
sha256: <64 hex>
source_url: https://github.com/Rudrabha/Wav2Lip  +  https://github.com/litongjava/live-talking
license_id: Wav2Lip-ResearchOnly   # 见 https://github.com/Rudrabha/Wav2Lip/blob/master/LICENSE
license_review: approved
runtime: <LiveTalking 启动参数>
functional_probe: <命令/测试 ID>
verified_at: <ISO-8601>
status: discovered|hashed|licensed|loadable|verified|blocked
```

商业化触发条件（NFR-10）：
- 任一时刻出现 "传播/分享/直播/导出/多用户" 关键词 → 立即停线。
- 重新评审顺序：① 替换为可商用数字人方案；② 获得原作者书面许可。
- 重新评审前不得发布或更新任何对外能力。

---

## 12. Draw.io 修补（修补 R-15）

- p6 r3 模型集成行单元格补：`→ 蓝色：5 Ports + 5 Adapters + ModelRegistry + license_review 子项 → M0 / AC-03/04/06/12`
- p4 L76-81 工时区名右侧增加 `↔ FR-08/09/10`、`↔ FR-12`、`↔ FR-15` 文字标注（FR→实体映射）。
- p5 swimlane A 顶部增加 `barge_in.detected` 节点（与 §5 第 8 步对齐）；state 框补 `error→listening|speaking|thinking 非法` 反例说明。
- p6 表格加 "状态" 列镜像 traceability-matrix（"未开发/部分已实现/已实现/需修改/待核验"）。
- p8 v2 区 v21 前增加 "V2 单独 ADR 触发条件" 节点：GPU 调度变化、模型宿主变化、外联能力出现任一即触发。

---

## 13. 保留任务可注入时钟（修补 I-12）

| 项 | 实现 |
|---|---|
| 时钟基准 | `ended_at + 30d`（UTC，自然日）；started_at 仅审计展示 |
| 注入方式 | 环境变量 `RETENTION_NOW=ISO8601`（优先级最高）+ `config/retention.toml` `now_override`；默认读取系统时钟 |
| 触发周期 | 启动时扫描一次 + 每日 03:00 本地时间定时任务（cron 形式由 RuntimeLauncher 触发） |
| 重试退避 | 指数退避，初始 60s，最大 6 次；最终失败写 `retention.failed` 审计与告警 |
| 不删长期记忆 | 保留任务只扫 `sessions` + `turns` + `session_transcripts` + `session_summaries`；不扫 `memories` / `memory_fts` / `memory_vectors` / `consents` / `profiles` / `asset_versions` |

AC-10 注入 29/30/31 天会话的 fixture 由 `tests/integration/fixtures/retention/` 提供；启动测试时设置 `RETENTION_NOW=now+30d+1s` 即可确定性清理。

---

## 14. 跨文档同步要求（修补一致性）

任何字段调整必须同批更新：
1. `PRD.md` §6/§7（NFR 数字）
2. `target-architecture.md` §5/§6/§7
3. `acceptance-plan.md` AC 硬门
4. `traceability-matrix.md` 当前状态
5. `model-manifest.md` §1/§4
6. `prototype-spec.md` §6/§7
7. `cyberWife-architecture-gap.drawio` 涉及页
8. 本文件 `implementation-contracts.md`（作为单一来源）

仅改一份视为偏移，参照 `target-architecture.md §11` 完整性规则。

---

## 15. 出门检查清单（历史基线，已由 §31/§35 取代）

- [x] 目录骨架唯一（I-01）
- [x] REST 端点全集（I-02）
- [x] WS 事件全集（I-03）
- [x] 状态机 6×6 完整（I-04）
- [x] 领域事件归属（I-05）
- [x] 数据表完整 + 维度固化（I-06、A7）
- [x] 取消传播契约（I-07）
- [x] 模型清单字段（I-09）
- [x] 验收硬门量化（I-10）
- [x] 资源预算互锁（I-11）
- [x] 保留任务可注入时钟（I-12）
- [x] Prompt 预算默认值（A8）
- [x] 浏览器20ms 帧合同（A10）
- [x] Avatar loopback H.264 WebSocket配置（A11，ADR-010）
- [x] 模型 fallback + 离线镜像（R-01）
- [x] WSL→Windows 解析（R-04）
- [x] audit_events 哈希算法 + 取证字段（R-06）
- [x] Wav2Lip LICENSE 引用（R-11）
- [x] Draw.io 修补（R-15）

**历史判定（不得作为当前启动授权）：实施合同补遗完成后可启动 M0；M0 通过后可启动 M1~M6。当前唯一启动与阶段门见 §31/§35。**

---

## 16. 错误码目录与 user_action 枚举（修补 AR-03）

`backend/cyberwife/api/errors.py` 输出下列常量；前端 i18n 表同步消费。所有错误响应均含 `{code,message,user_action,trace_id,retryable}`，HTTP 状态与 code 解耦。

| code（命名空间） | HTTP 默认 | message 文案（中文） | user_action 取值 | retryable | 触发场景 |
|---|---|---|---|---|---|
| `auth.consent_required` | 403 | "请先完成授权" | `open_onboarding` | false | FR-02 未授权访问资产 |
| `consent.revoked` | 409 | "已撤销授权，请重新授权" | `open_onboarding` | false | FR-02 撤销后再上传 |
| `asset.invalid` | 422 | "文件校验未通过" | `open_settings` | false | magic bytes / 尺寸 / 解码失败 |
| `asset.too_large` | 413 | "文件超过 50MB" | `open_settings` | false | FR-04/05 |
| `asset.version_conflict` | 409 | "版本冲突，请刷新" | `retry` | true | 乐观并发 |
| `session.not_found` | 404 | "会话不存在" | `none` | false | DELETE 已结束 |
| `session.recording_policy_invalid` | 422 | "会话录制策略无效" | `none` | false | FR-13 |
| `memory.not_found` | 404 | "记忆不存在" | `none` | false | FR-12 |
| `memory.confirm_required` | 412 | "请二次确认" | `confirm_dialog` | false | FR-12 全清 |
| `audit.entity_not_found` | 404 | "审计实体不存在" | `none` | false | G3 复核 |
| `retention.invalid_clock` | 422 | "时钟参数无效" | `none` | false | RETENTION_NOW 解析失败 |
| `health.component_unavailable` | 503 | "组件不可用" | `retry_later` / `open_status` | true | FR-15 |
| `health.degraded` | 200 | "已降级" | `open_status` | false | 组件 degraded |
| `frame.size_limit` | 413 | "音频帧超过 4KB" | `none` | false | §7 WS 二进制帧 |
| `turn.cancelled` | 200 | "本轮已取消" | `none` | false | FR-09 打断 |
| `turn.late_event` | 200 | "迟到事件已丢弃" | `none` | false | event_seq/turn_id 过期 |
| `interrupted` | 200 | "已切换到 listening" | `none` | false | barge_in 完成 |
| `internal.error` | 500 | "内部错误" | `retry_later` | true | 未分类异常 |

`user_action` 取值枚举：`open_onboarding` / `open_settings` / `open_status` / `retry` / `retry_later` / `confirm_dialog` / `none`。前端按此分发到对应入口；未在枚举中的 user_action 视为后端 bug，记录到 `audit_events.action='internal.error'`。

---

## 17. `config/default.example.toml` 字段集中键表（修补 AR-04）

```toml
# ── 进程与端口 ──────────────────────────────────
[server]
bind = "127.0.0.1"
gateway_port = 7860
speech_port   = 8091
avatar_port   = 8010
llama_host    = "127.0.0.1"           # 由 ResolveWindowsHost.ps1 覆盖
llama_port    = 8090
shutdown_grace_seconds = 10

# ── 路径（仅相对/受控路径，禁绝对私有路径）────
[paths]
workspace      = "C:\\workSpace\\cyberWife"
data_root     = "/mnt/cw\\u002ddata"   # WSL2 ext4，禁 Windows 挂载盘
assets_root   = "/mnt/cw\\u002ddata/assets"
logs_root     = "/mnt/cw\\u002ddata/logs"
migrations_dir = "migrations"
salt_file     = "config/.salt"        # 启动时生成，仅本机

# ── 数据库 ──────────────────────────────────────
[db]
path          = "/mnt/cw\\u002ddata/cyberwife.db"
wal           = true
cache_size_kb = 2_048
synchronous   = "NORMAL"

# ── 模型（只引用 logical_id，由 model-registry.local.yaml 解析）──
[models]
vad           = "silero-vad-v5"
asr           = "faster-whisper-large-v3-turbo"
llm           = "qwen3-14b-instruct-q4_k_m"
tts           = "cosyvoice2-0.5b"
avatar        = "livetalking-wav2lip256"
embedding     = "bge-small-zh-v1.5"

# ── 设备与精度 ──────────────────────────────────
[device]
asr_compute_type   = "float16"
tts_compute_type   = "float16"
llm_gpu_layers     = 40
avatar_resolution  = 256
avatar_fps         = 25

# ── Prompt 预算（详见 §6）─────────────────────
[prompt]
max_context_tokens   = 4096
profile_max_tokens   = 600
short_term_count     = 3
short_term_max_tokens= 300
vector_top_k         = 4
vector_score_min     = 0.55
fts_top_k            = 6
memory_budget_tokens = 800

# ── 取消与打断（详见 §5/§7/§18）──────────────
[cancel]
audio_silence_p95_ms = 400
audio_silence_max_ms = 1000
llm_cancel_deadline_ms = 1000
tts_cancel_deadline_ms = 1000
avatar_drain_deadline_ms = 1000

# ── 保留（详见 §13）─────────────────────────
[retention]
session_ttl_days = 30
scan_startup     = true
scan_cron_local  = "03:00"
retry_initial_s  = 60
retry_max_n      = 6
inject_env       = "RETENTION_NOW"

# ── 日志（详见 §4/§9）───────────────────────
[logging]
level            = "INFO"
redact_sensitive = true
fields_blacklist = []  # 仅表示已批准撤销前端字段白名单；后端强制脱敏门见 §34/§35

# ── 浏览器（详见 §7/§8）────────────────────
[browser]
audio_sample_rate = 16000
audio_channels    = 1
audio_frame_ms    = 20
ws_binary_max_bytes = 4096
avatar_video_transport = "ws_h264"   # ADR-010；loopback Annex-B/WebCodecs
avatar_video_queue_limit = 2
```

每个字段在合同与实现侧唯一化；新增字段需更新本节并提交 ADR。

---

## 18. 取消令牌传播的 API 细节（修补 AR-09）

| 端 | 库/对象 | 调用 |
|---|---|---|
| HTTP（llama-server） | `httpx.AsyncClient` + `asyncio.timeout` | `client.send(req, stream=True)`，取消时 `await client.aclose()` 触发 `httpx.RemoteProtocolError` 终止流；同时 `request_id` 携带 cancel token，llama.cpp 侧按 stop 标记丢弃后续 token |
| TTS 队列（Qwen3-TTS） | `asyncio.Queue` + 取消令牌 | 队列消费协程 `while not cancel_token.cancelled(): item = await q.get()`；cancel_token 是 `asyncio.Event`；设置后消费循环在下一次 await 立即抛 `CancelledError`；未消费的 chunk 由 finally 清理 |
| 浏览器播放缓冲 | `AudioContext` + `AudioBufferSourceNode` | `source.stop()` 立即停止当前 `AudioBufferSourceNode`，并把 `MediaSession` 的 playbackState 置 `paused`；不调用 `audioCtx.suspend()`（避免影响 VAD 输入）；下一帧 source 切换为 `idle` |
| Avatar队列（LiveTalking） | `AvatarPort` PCM + H.264 WebSocket帧队列 | cancel时`flush_talk()`清音频特征；浏览器按generation丢弃迟到帧；断开WS清理渲染session；每客户端队列≤2且只丢视频 |
| 浏览器端 UI 状态 | React `ConversationClient` | 收到 `barge_in.detected` 即设本地 cancel flag + 调用 `MediaSession.cancel()`；迟到 `event_seq` 在 `ConversationScreen` reducer 内丢弃 |

| deadline | 含义 | 超时动作 |
|---|---|---|
| `audio_silence_p95_ms = 400` | AudioContext stop + 用户感知静音达标 | 接受 |
| `audio_silence_max_ms = 1000` | 取消传播硬上限 | 超时则清Gateway播放与Avatar输入队列并broadcast `component.degraded(reason='cancel_timeout')`；不关闭共享视频WS |
| `llm_cancel_deadline_ms = 1000` | httpx aclose + llama.cpp stop 标记生效 | 超时记 `audit.health.degraded`，UI 进入 degraded 横幅但保持 listening |

---

## 19. 14×6 领域事件归属矩阵（修补 RR-05）

`target-architecture.md §4` 6 个聚合/服务边界上下文共 6 类责任实体。本表给出 14 领域事件 × 6 责任实体的发布/订阅矩阵（P = 发布，* = 订阅）。

| 领域事件 | AssetService | ConversationOrchestrator | TurnPipeline | MemoryService | RetentionService | HealthAggregator |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `ConsentGranted` | P | * | | | | |
| `AssetActivated` | P | * | | | | |
| `SessionStarted` | | P | * | | | |
| `UtteranceFinalized` | | * | P | | | |
| `TurnStarted` | | P | * | | | |
| `ReplyChunkReady` | | * | P | | | |
| `PlaybackStarted` | | * | P | | | |
| `BargeInDetected` | | P | * | | | |
| `TurnCancelled` | | P | * | | | |
| `SessionEnded` | | P | * | * | | |
| `MemoryCommitted` | | | | P | * | |
| `MemoryDeleted` | | | | P | * | |
| `RetentionExpired` | | | | * | P | |
| `ComponentDegraded` | | * | * | * | | P |

读法：例如 `BargeInDetected` 由 `ConversationOrchestrator` 在收到客户端 `turn.cancel` 后触发；`TurnPipeline` 订阅以清理其 TTS/Avatar 子队列；`HealthAggregator` 不订阅，仅接收其显式降级事件。

---

## 20. 草稿表 schema 与 M2 onboarding 状态（修补 RR-13）

```sql
CREATE TABLE onboarding_drafts (
  id INTEGER PRIMARY KEY CHECK (id = 1),       -- 单线草稿
  consent_granted     INTEGER NOT NULL DEFAULT 0,  -- 0/1
  step_completed       INTEGER NOT NULL DEFAULT 0,  -- 0..4（4 表示完成）
  asset_consent_at     TEXT,
  profile_draft_json   TEXT NOT NULL DEFAULT '{}', -- 五步输入全量 JSON
  settings_json        TEXT NOT NULL DEFAULT '{}', -- 运行检查/照片/声音选择/逐字稿
  device_snapshot_json TEXT NOT NULL DEFAULT '{}', -- 设备/GPU/磁盘/麦克风快照
  updated_at           TEXT NOT NULL
);

CREATE TABLE profile_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id),
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

- 五步每一步的"草稿字段集合"统一写入 `profile_draft_json`，version 字段复用 profiles.version；提交时由 SQLite 事务原子替换并归档到 profile_history。
- 撤销授权：`onboarding_drafts.consent_granted=0` 但**不删除**草稿；UI 顶部红条提醒用户；用户在同 session 内可重新勾选继续续接。
- 草稿与正式配置边界：`onboarding_drafts` 是单线中间态（id=1）；`profiles` 是已保存版本；`profile_history` 留档。
- 幂等键：`PUT /api/v1/onboarding/draft` 接受 `If-Match: draft_version`；服务端比较 `step_completed` 与请求步数决定是否拒绝。

---

## 21. a11y 自动审计工具与硬门槛（修补 RR-14）

| 工具 | 用途 | 最低版本 | 集成层 | 失败硬门槛 |
|---|---|---|---|---|
| `axe-core/playwright` | 静态 ARIA/对比度/焦点属性 | 4.10 | e2e | 每页 0 critical / 0 serious |
| `pa11y-ci` | 命令行 a11y 报告 | 1.11 | contract | 三档分辨率 + 三档主题 = 18 报告，全部 0 errors |
| `prefers-reduced-motion` 模拟 | Playwright `emulateMedia({reducedMotion:'reduce'})` | 内建 | e2e | 必要信息在 reduced-motion 下可见，断言非 0 行隐藏 |
| 焦点圈闭断言 | Playwright DOM Tab 序列 + 焦点恢复 | 内建 | e2e | 模态打开时焦点进入内部，关闭后回到触发点 |
| `aria-live` 轮询断言 | Playwright `getByRole('status')` + waiting | 内建 | e2e | 状态变化 ≤1s 内 `polite` 区域更新；error ≤200ms `assertive` |
| 读屏兼容性 | `NVDA 2025.x` + Firefox | NVDA 2025.1 | human review | 六态标签均被正确朗读（人工 5/5） |

`AC-11` 自动审计硬门槛：axe-core 0 critical + pa11y-ci 0 errors + reduced-motion 100% 信息保留 + 焦点圈闭 100%。任一不达标即 AC-11 fail，必须修复后重测。

---

## 22. 端点 ↔ FR-XX 显式映射（历史子集，终态以 §28 为准）

`docs/traceability-matrix.md` 应在"数据/接口"列添加端点路径。下列映射为最终合同：

| 端点 ↔ 责任 | 关联 FR/NFR |
|---|---|
| `GET/PUT /api/v1/onboarding/draft` | FR-01 五步草稿/重启续接 |
| `GET/POST /api/v1/consents` | FR-02 授权授予/撤销 |
| `GET /api/v1/assets/{portrait\|voice}` | FR-04/05 列出/历史版本（回退） |
| `POST /api/v1/assets/{id}/activate` | FR-04/05 原子激活 |
| `POST /api/v1/assets/{id}/avatar-builds` | 为授权照片创建静态安全版本；生成失败时仍可保留静态人物 |
| `POST /api/v1/avatar-builds/{id}/idle-generation` | 排队执行互斥的本机正面化与10秒Idle生成；同一时刻仅一个任务 |
| `GET /api/v1/avatar-builds/{id}/idle-generation` | 返回落盘状态、阶段和进度，不返回私有路径 |
| `GET /api/v1/avatar-builds/{id}/idle-generation/{frontal\|video}` | 仅在待审/已激活状态提供 `private, no-store` 预览 |
| `POST /api/v1/avatar-builds/{id}/idle-generation/approve` | 服务端视觉确认门；构建视频Avatar并原子激活同源照片/数据 |
| `PATCH /api/v1/sessions/{id}/no_record` | FR-13 本次不记录会话内切换 |
| `GET /api/v1/audit?entity=&action=` | NFR-04/G3 数据隐私复核（无独立 FR 行，对应 G3） |
| `GET /api/v1/retention/now` | FR-14 30 天保留查询 |
| `POST /api/v1/launcher/recover` | FR-17 一键恢复 |

`traceability-matrix.md` 数据/接口列需按上表刷新；G3 数据隐私复核列写 `/audit`。

---

## 23. 温箱基线数值与漂移区间（修补 RR-10）

| 指标 | 基线（22°C 室温，GPU 待机 ≤40°C） | 可接受漂移 | 不可接受 |
|---|---:|---:|---|
| LLM P50/P95 | 1.6s / 2.9s | +20% | +50% |
| 打断 P95 | 320ms | +25% | +60% |
| Avatar inferfps / finalfps | 30 / 28 | -3 / -3 | < 25 |
| RAM 利用率 | 22GB | +2GB | > 26GB |
| GPU 温度 | 65°C | +15°C | > 85°C 触发降频 |
| 队列深度 | ≤4 帧（Avatar）/ ≤16 chunk（TTS） | ×2 | 持续单调上升 |
| 数据库大小 | +2MB/小时（不记录模式 +0） | ×2 | > 30MB/小时 |

`tests/performance/soak_1h.py` 实测时把上述基线写入 `config/performance_baseline.json`。本表只用于趋势告警；经G-LAT7批准，PRD/AC-04的首响硬门为P95≤7.0s，P50必须记录但不设硬门，P95越界直接失败。

---

## 24. 第二轮出门检查清单（历史基线，已由 §31/§35 取代）

- [x] xxxx
- [x] 14×6 领域事件归属（RR-05）
- [x] M2 草稿表 schema（RR-13）
- [x] a11y 工具与最低版本（RR-14）
- [x] 温箱基线数值（RR-10）
- [x] 端点 ↔ FR 映射（RR-18）
- [x] 错误码目录（AR-03）
- [x] example.toml 字段表（AR-04）
- [x] 取消令牌具体 API（AR-09）
- [x] JSON Schema 路径（AR-02，由 M1-02 承接）
- [x] 各 adapter 契约测试 ID（AR-06，由 M1-02 承接）
- [x] 前端禁止 localStorage 字段清单（AR-15，M1-07 承接）

**历史判定（不得作为当前启动授权）**：内审已无阻塞项；当时可启动 M0。当前唯一启动与阶段门见 §31/§35。

---

## 25. JSON Schema 字段级指引（修补 AR-02）

`schemas/` 下每个 .schema.json 必须符合 JSON Schema Draft 2020-12，遵循下列统一骨架（以 `rest/error_envelope.schema.json` 为例）：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://cyberwife.local/schemas/rest/error_envelope.schema.json",
  "title": "REST 错误响应统一信封",
  "type": "object",
  "additionalProperties": false,
  "required": ["code", "message", "user_action", "trace_id", "retryable"],
  "properties": {
    "code":         { "type": "string", "enum": [<§16 18 个 code>] },
    "message":      { "type": "string", "minLength": 1, "maxLength": 200 },
    "user_action":  { "type": "string", "enum": ["open_onboarding","open_settings","open_status","retry","retry_later","confirm_dialog","none"] },
    "trace_id":     { "type": "string", "pattern": "^[0-9A-HJKMNP-TV-Z]{26}$" },
    "retryable":    { "type": "boolean" }
  }
}
```

WS 公共 envelope（`ws/envelope.schema.json`）：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WS 公共信封 6 字段",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "session_id", "turn_id", "event_seq", "occurred_at", "payload"],
  "properties": {
    "type":         { "type": "string", "minLength": 1 },
    "session_id":   { "type": "string", "pattern": "^[0-9]+$" },
    "turn_id":      { "type": ["null","string","integer"], "minimum": 0 },
    "event_seq":    { "type": "integer", "minimum": 0 },
    "occurred_at":  { "type": "string", "format": "date-time" },
    "payload":      { "type": "object" }
  }
}
```

每个端点 schema 必含：`required` 列表 + `additionalProperties:false` + `enum`/`pattern`/`format` 约束；时间字段统一 `date-time`；trace_id 统一 ULID 26 字符 Crockford 正则；session_id 统一 64-bit 整数字符串。

contract test fixture 路径：`tests/contract/fixtures/rest/*.json`、`tests/contract/fixtures/ws/*.json`。M1-02 第一周交付 17 个 REST + 8 个 WS + 1 个 domain_events = 26 个 schema。

---

## 26. ~~前端 localStorage 黑/白名单~~（已撤销，2026-09-24 V1.2 范围变更）

> **本章节自 2026-09-24 V1.2 范围变更起撤销**。详见 `docs/V1.2-redline-removal-authorization.md` v0.2。
>
> **撤销内容**：
> - §26.1 黑名单（14 项字段不进 localStorage）
> - §26.2 白名单（仅 4 项可写 localStorage）
> - §26.3 IndexedDB 边界（禁止业务键值）
> - §26.4 测试（仅出现白名单 4 key 断言）
> - §26.5 引用关系（§4 ⊇ §26.1）
>
> **撤销后**：localStorage / sessionStorage / IndexedDB 完全放开；任何字段可写；§26 自动化审计门槛归零。
> 用户（李玄，1146456789@qq.com）2026-09-24 显式接受 4 项 P0 风险：
> 1. NFR-06 日志脱敏空壳化
> 2. NFR-04 敏感数据可入 Git
> 3. P0-1 Windows Defender 自动索引
> 4. P0-2 Git commit 泄露

---

## 27. deadline 完整表（修补 AR-09 + §17 一致性）

§17 `[cancel]` 段声明 5 项 deadline。§18 deadline 表补齐 5 行保持两表一致：

| 字段 | 默认 | 含义 | 超时动作 |
|---|---:|---|---|
| `audio_silence_p95_ms` | 400 | AudioContext stop + 用户感知静音 P95 | 接受 |
| `audio_silence_max_ms` | 1000 | 取消传播硬上限 | 强制关闭 RTCPeerConnection + broadcast `component.degraded(reason='cancel_timeout')` |
| `llm_cancel_deadline_ms` | 1000 | httpx aclose + llama.cpp stop 标记生效 | 记 `audit.health.degraded`，UI 显示横幅但保持 listening |
| `tts_cancel_deadline_ms` | 1000 | asyncio.Queue drain + asyncio.Event token 生效 | 丢弃未消费 chunk，UI 显示"已跳过剩余语音"，不进入 error |
| `avatar_drain_deadline_ms` | 1000 | LiveTalking queue.shutdown(immediate=True) + ≤16 frames 丢弃 | 静态 Avatar 降级 + `component.degraded` 广播，下一轮自动重试 |

§17 `[cancel]` 段已含全部 5 项；本表与 §18 deadline 表一一对应。

---

## 28. 端点 ↔ FR 显式映射（终态，补 §22 全 17 端点）

| 端点 | 责任实体 | 关联 FR/NFR |
|---|---|---|
| `GET /api/v1/health` | HealthAggregator | FR-15/NFR-03 |
| `POST /api/v1/health/{component}/retry` | HealthAggregator | FR-15 |
| `GET/PUT /api/v1/profile` | AssetService/repository | FR-06 |
| `GET/PUT /api/v1/onboarding/draft` | SettingsService | FR-01 |
| `GET/POST /api/v1/consents` | AssetService | FR-02 |
| `GET /api/v1/assets/{portrait\|voice}` | AssetService | FR-04/05 |
| `GET/PUT /api/v1/assets/{portrait\|voice}/preview` | AssetService | FR-04/05 |
| `POST /api/v1/assets/{id}/activate` | AssetService | FR-04/05 |
| `POST /api/v1/sessions` | ConversationOrchestrator | FR-08/FR-13 |
| `PATCH /api/v1/sessions/{id}/no_record` | ConversationOrchestrator | FR-13 |
| `DELETE /api/v1/sessions/{id}` | ConversationOrchestrator | FR-08 |
| `GET /api/v1/memories?q=` | MemoryService | FR-12 |
| `PATCH/DELETE /api/v1/memories/{id}` | MemoryService | FR-12 |
| `DELETE /api/v1/memories` | RetentionService | FR-12 |
| `GET /api/v1/audit?entity=&action=` | RetentionService | NFR-04/G3 |
| `GET /api/v1/retention/now` | RetentionService | FR-14 |
| `POST /api/v1/launcher/recover` | ApiGateway | FR-17 |

WS 事件全集（与 envelope 6 字段配套）：

| 事件 | 方向 | 关联 FR |
|---|---|---|
| `audio.chunk` | C→S | FR-08 |
| `conversation.stop` | C→S | FR-08 |
| `turn.cancel` | C→S | FR-09 |
| `privacy.no_record` | C→S | FR-13 |
| `audio.device_lost/back` / `audio.level` | C→S | §7 |
| `state.changed` | S→C | FR-07 |
| `transcript.partial/final` | S→C | FR-08 |
| `reply.text.delta/final` | S→C | FR-08 |
| `reply.audio.chunk` | S→C | FR-08 |
| `reply.audio.started` | S→C | FR-07/§8 |
| `barge_in.detected` | S→C | FR-09 |
| `turn.cancelled` | S→C | FR-09 |
| `component.degraded/recovered` | S→C | FR-15 |
| `session.expired` | S→C | FR-14 |
| `error` | S→C | §16 |

---

## 29. profile_history FK ON DELETE 声明（修补 RR-13）

```sql
CREATE TABLE profile_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

语义：`profiles` 删除时 `profile_history` 必须保留；删除 profiles 由应用层先迁移 history 到 `archive_profiles` 表，再删除；不允许 FK CASCADE 删除历史版本。

---

## 30. 第三轮出门检查清单（历史基线，已由 §31/§35 取代）

- [x] schemas/ 目录骨架（§1）
- [x] JSON Schema 字段级指引（§25）
- [x] 前端 localStorage 黑/白名单（§26）
- [x] deadline 完整 5 项（§27）
- [x] 端点 ↔ FR 全 17 REST + 15 WS 映射（§28）
- [x] profile_history ON DELETE RESTRICT（§29）
- [x] 跨文档 §1–§24 引用升级

**历史判定（不得作为当前启动授权）**：内审无阻塞项；当时可启动 M0。当前唯一启动与阶段门见 §31/§35。

---

## 31. 2026-09-24 后端重基线（取代 §30 的启动结论）

用户已批准 G-UX，并要求后续重点转向后端。§30 的“可启动 M0”是旧里程碑结论，现被本节取代：当前进入 [`backend-development-plan.md`](backend-development-plan.md) 的 DOC-B 文档门；只有人类批准新版 Draw.io 和后续外部文档审查通过后，才允许启动 DEV-B0。

前端体验冻结不等于后端已实现。仓库实体必须按以下证据等级标注：

| 等级 | 含义 | 能否作为 V1 出门证据 |
|---|---|---|
| `present` | 文件/类/接口存在 | 否 |
| `contract_passed` | mock 或 schema 测试通过 | 否 |
| `runtime_verified` | 目标硬件真实模型最小功能探针通过 | 仅可通过阶段门 |
| `e2e_accepted` | 对应 AC 场景、性能和隐私门全部通过 | 是 |

## 32. 统一取消令牌合同

```text
CancellationToken {
  session_id: int
  turn_id: int
  generation: int
  cancelled_at_monotonic_ns: int | null
  cancelled_at_wall_utc: datetime | null
  reason: barge_in | session_stop | timeout | component_failure
}
```

- 每个 active turn 只能有一个当前 generation；创建新 turn 或确认 barge-in 时原子递增。
- LLM/TTS/Avatar adapter 和所有持久化入口接收 token；在产生 chunk 或副作用前比较 generation。
- `cancel()` 幂等；已取消 token 不可复用；迟到 chunk 只计指标，不向前端、播放器、Avatar 或数据库传播。
- 取消顺序不是串行等待：标记 token、关闭 LLM stream、停止 TTS、purge 浏览器/Avatar 队列并行执行；最终统一确认 `turn.cancelled`。
- `audio_silence_p95_ms=400` 是用户门槛，`*_deadline_ms=1000` 是组件强制回收上限，两者不得混用。
- `cancelled_at_monotonic_ns` 只与同一 clock-correlation 区间的浏览器/服务采样比较；`cancelled_at_wall_utc` 只用于日志排序，不得参与延迟计算。

## 33. Functional probe 与 ready 合同

`ModelRegistry.status` 只描述资产验证状态，不能直接映射为运行组件 `ready`。HealthAggregator 必须调用运行实例的 functional probe：

| 组件 | ready 必需条件 |
|---|---|
| LLM | 目标 revision 实际加载并流式返回≥1 token |
| VAD/ASR | 静音不误触发且授权 fixture 产生 final |
| TTS | 默认非TensorRT CosyVoice2产生可解码、非静音、内容正确音频；Qwen仅在显式回退profile验证 |
| Avatar | 临时 session 接受短音频并输出连续帧与 FPS |
| Embedding | 512维生成及 sqlite-vec insert/search/delete 往返 |

探针失败时状态只能是 `loading/degraded/error`；PID、监听端口、模型路径或哈希通过均不能单独提升为 `ready`。

## 34. §26 风险接受的适用边界

§26 记录的前端浏览器存储放开属于历史范围变更，不撤销 PRD NFR-04/NFR-06 对后端、日志、Git、原始音频、逐字稿、记忆和私有资产的隐私要求。V1 总验收仍必须满足：

- 原始麦克风音频落盘增量=0；
- 未声明出站请求=0，监听仅 loopback；
- 日志无完整 prompt/逐字稿/人设正文/绝对私有路径；
- Git 无模型、数据库、用户资产和运行日志；
- no-record 会话的业务持久化增量=0；
- 删除后源记录、FTS、vector 和派生缓存召回=0。

如需再次放宽这些后端边界，必须作为新的 PRD 范围变更单独批准，不能引用 §26 自动推导。

### 34.1 §26 与现行 PRD 的逐项对账

后续 G-OX、B2.5/B2 与本轮 B3—B5 架构批准晚于 §26，并恢复了后端发布硬门；只保留“浏览器存储不设字段白名单”这一范围变化。

| §26 历史接受项 | 现行口径 | 缓解/验收 | 残留风险 |
|---|---|---|---|
| NFR-06 日志脱敏空壳化 | **已被后续批准取代**；后端日志必须脱敏 | AC-13 正则/熵/路径扫描，完整正文0 | 浏览器本地调试存储仍可能含用户数据，由用户承担本机风险 |
| NFR-04 敏感数据可入 Git | **已被后续批准取代**；Git 私有资产/DB/模型/日志0 | AC-13 全历史与工作树扫描 | 用户手工绕过项目工具不在自动化保证内 |
| Windows Defender 自动索引 | 接受 OS 对已放开的浏览器存储进行本机索引 | 私有数据仍不得进入项目日志/Git；卸载不隐删 | 本机管理员/OS 可读取浏览器数据 |
| Git commit 泄露 | 仅接受用户手工将浏览器导出物提交的风险；项目不得自动提交 | `.gitignore`、提交前扫描、B5证据 | 用户绕过钩子仍可能泄露 |

这不是撤销用户对浏览器本地存储的风险接受，而是明确后续批准的 PRD NFR-04/NFR-06 对项目后端和发布物继续生效。

## 35. B0～B5 当前唯一实施与验收补充合同

本节根据 2026-09-24 外部独立审查建立，优先于 §15、§22、§23、§24、§30 的历史结论；§28 是 REST/WS 端点映射唯一终态。

- **证据等级**：mock/内存替身只能形成 `contract_passed`；真实模型、真实数据和目标硬件依次形成 `runtime_verified`、`e2e_accepted`，不得跳级。
- **前端存储边界**：保留已批准的 §26 撤销，不恢复 localStorage/IndexedDB 白名单；但 §34 的后端日志、Git、原始音频、no-record、删除与网络边界仍是 B5 硬门。
- **VRAM**：同时保存 NVML 应用进程占用、CUDA device free delta 与原始 `nvidia-smi`。出门指标是本项目所有进程可归因峰值≤22GB；两种设备级读数差异>1GB 时验收失败并调查，不得任选较小值。
- **RAM**：Windows项目进程private bytes + WSL项目进程RSS峰值≤14GB；宿主`Available MBytes`与WSL `MemAvailable`均不得低于2GB且不得持续swap-in。working set单列诊断，避免GGUF mmap重复计量。当前15.52GiB WSL上限有效，不要求扩至28GB。
- **网络**：允许集合仅为 loopback 与运行时解析并记录的 Windows↔WSL 本机桥接地址。非允许集合的 DNS、HTTP、TCP 已建立连接数必须为 0。
- **TTS**：按ADR-008，V1默认使用 `cosyvoice2-0.5b` FP16流式非TensorRT profile；O3R真实Edge 30/30、P50/P95=5.567/6.392秒且资源达门。`qwen3-tts-12hz-1.7b-base` adapter和显式启动profile保留回退，禁止双TTS常驻。
- **Embedding**：固定 `bge-small-zh-v1.5` 512 维。sqlite-vec 未加载、维度不符或往返失败时启动阻断，禁止以内存索引或 FTS-only 冒充 ready。
- **磁盘**：实际剩余空间<10GB 时阻止新的模型/推理/派生缓存写入并提示；用户业务写入采取 fail-safe，不自动删除既有数据。
- **延迟与打断**：AC-04首响P95≤7.0s不允许基线漂移，P50继续报告；AC-05 P95≤400ms 是用户门槛，1000ms 只是组件回收 deadline。
- **WS 标识**：`session_id` 是十进制字符串；二进制帧 `turn_id` 是 session 内单调 uint32；`chunk_seq` 是单 turn 内 uint16，禁止回绕。
- **恢复**：AC-12 的主验收入口是 `POST /api/v1/launcher/recover`；UI 操作只验证其用户路径，不得用 UI 假状态代替进程恢复。
- **FR-19**：保持 Should，不阻塞 G1；浏览器 HostBridge 安全空实现仍须通过合同回归。
- **B4 数据来源**：最终验收只接受 B3 已 `e2e_accepted` 的真实 session/turn，不接受 mock session。

## 36. B3～B5 唯一补充合同

- **全双工 WS**：每 session 为持续 receiver + 单 active-turn task + 有界 outbound queue + 单 sender。receiver 不等待推理，所有发送只经 sender。
- **浏览器取消**：`MediaSession.cancelGeneration(generation)` 停止旧播放 source 并清理 marker；不得关闭输入 AudioContext。Avatar和字幕 reducer同样按 generation 丢弃。
- **无记录 ID**：创建即none时使用从 `2**62` 起的进程内十进制ID；不插入sessions。会话中开启后删除整场业务记录且不可逆，允许保留无正文审计。
- **记忆固化**：置信度≥0.80固化；0.60～0.79只作进程内待确认候选；<0.60丢弃。FTS top-6、vector top-4、cosine≥0.55、最终≤4条且≤800 token。
- **事务所有权**：MemoryRepository独占BEGIN/COMMIT/ROLLBACK；VectorIndex不得内部commit。`DELETE /api/v1/memories`要求JSON `confirmation=PURGE_ALL`。

## 37. B3—B5 外审闭环补充

- **时间语义**：`cancelled_at_monotonic_ns` 只在本机进程与浏览器 correlation 区间内比较；对外 `occurred_at` 为 UTC ISO-8601。证据必须保存 correlation 采样，禁止直接相减两台时钟。
- **资源口径**：“启动前约16GB可用”指启动采样点的 Windows `\Memory\Available MBytes`，不是项目配额；“0.3GiB余量”是 B2 运行峰值相对≥2GB安全线的剩余额度快照。每次验收重新采样，项目 private bytes+WSL RSS≤14GB、Windows/WSL available各≥2GB同时成立。
- **趋势门**：采用 [`acceptance-command-manifest.md`](acceptance-command-manifest.md) §5 的5秒采样和斜率阈值；验收工具单列但仍计入宿主 available 硬门。
- **磁盘低水位**：测量 `~/.cyberWife` 所在卷的可用空间；<10GiB阻止可重建缓存，不阻断已开始的数据库事务与脱敏安全审计。先轮转日志；不得自动删除资产、数据库、备份或长期记忆。
- **TTS 回退所有者**：`HealthAggregator` 根据启动probe、同一发布候选30条普通链P95>7秒、CER>5%或资源越门触发 CosyVoice→Qwen 一次性降级；禁止双常驻与自动抖动切回。用户发起单项恢复且 CosyVoice probe 通过后，下一会话才可恢复默认。
- **no-record 内存ID**：仅 Orchestrator 内部使用；不得进入 envelope、日志、audit、错误码或浏览器。B4 必须扫描 WAL、audit与loopback抓包确认无痕。
- **网络允许集合**：loopback + 本次启动解析并记录的 Windows↔WSL 本机桥接地址；集合外归属于项目PID的 DNS、HTTP、TCP 已建立连接必须为0。
- **schema迁移**：数据库持有单调 `PRAGMA user_version`；每次迁移先备份、在副本上做升级/降级可逆性测试，再原子替换。B5 冻结 migration 哈希；不可逆迁移必须阻断并要求明确备份确认。
- **保留边界**：过期判断为`expires_at < now`；等于30天不删。长期记忆不在扫描表中。
- **B5先补功能**：授权撤销、资产版本激活/回退、完整人设并发和默认沉浸式入口完成后，才可运行AC全集。
- **文档优先级**：PRD → 本合同/目标架构 → 阶段plan/acceptance →实现。历史M文档和旧评审页只作证据，不得覆盖本节。
