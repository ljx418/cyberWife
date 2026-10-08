# V2-X 实现合同

**版本**：1.0  
**适用范围**：V2-X0～X9；V2-A不在本合同内

## 1. 总体约束

- 保持模块化单体；浏览器、Gateway、Speech worker、Avatar worker和Windows LLM的部署拓扑不变。
- 单一活动角色、单一会话、单一可见人物表面。新增能力通过独立feature flag接入并可退回V1。
- 资源硬门：项目不可回收RAM峰值≤14GB、VRAM≤22GB、宿主/WSL余量≥2GB；重型离线生成与实时对话模型禁止双常驻。
- 性能硬门保持普通首响P95≤7秒、有效打断P95≤400ms；任何V2-X能力不得以放宽V1门出门。

## 2. 具体代码实体

| 层 | 实体/目标文件 | 状态 | 职责与禁止事项 |
|---|---|---|---|
| UI | `prototype/src/App.tsx` | 修改 | 只编排导航和现有ConversationScreen；不得继续承载新增领域逻辑 |
| UI | `features/devices/DevicePanel.tsx` | 新增 | 设备枚举、短时校准、自动/PTT切换；不自行决定后端VAD |
| UI | `features/audio/OutputControls.tsx` | 新增 | 音量、静音、当前回答重播、可选sink；重播不持久化 |
| UI | `features/assets/SourcePackPanel.tsx` | 新增 | 同一活动角色多源素材、授权和状态；不出现角色切换 |
| UI | `features/stage/StageControls.tsx` | 新增 | 构图、场景、外观和降级提示；所有切换由服务端active revision确认 |
| UI | `features/memory/MemoryWorkbench.tsx` | 从Settings拆分 | CRUD、候选、分组、只读关系图；外部插件入口禁用 |
| 前端服务 | `InputAudioSessionController` | 修改 | `deviceId`约束、校准样本、迟滞/最小持续、PTT门；活动track≤1 |
| 前端服务 | `SessionLifecycleController` | 新增 | visibility/network/health/generation统一恢复；旧generation不得复活 |
| 前端服务 | `MediaSession` | 修改 | Gain/Compressor、内存重播、sink渐进增强、音频主时钟 |
| 前端服务 | `AvatarSessionController` | 修改 | 帧年龄/冻结/漂移观测、迟滞质量档、过期帧丢弃；不暂停音频追帧 |
| 前端服务 | `StagePresentationController` | 新增 | Idle/微动作/live单表面状态机；素材缺失回退approved Idle |
| 平台 | `HostBridge` + `PwaBridge` | 修改/新增 | 全屏、安装能力检测；不引入Electron/Tauri前提 |
| API | `backend/cyberwife/api/server.py` | 修改 | 只做schema校验、鉴权边界和application调用；不得实现业务规则 |
| Application | `ExperienceSettingsService` | 新增 | flag、输入/输出/质量/语气偏好，乐观版本和安全默认值 |
| Application | `SourcePackService` | 新增 | manifest事务、哈希/授权/来源、active revision、回滚 |
| Application | `ScenePresetService` | 新增 | scene/appearance/rendition原子激活，失败保留旧revision |
| Application | `VisualClaimService` | 新增 | 本地候选→用户确认/拒绝；仅confirmed可供Prompt/Memory读取 |
| Application | `MemoryGraphService` | 新增 | 从内置记忆派生节点、边、分组；删除传播；不成为权威写存储 |
| Application | `VoiceStylePolicy` | 新增 | 已验证的提示/分句/推理参数预设；失败独立回退default |
| Application | `QualityGovernor` | 新增 | 基于队列年龄/漂移/冻结的迟滞分级；只发质量策略，不接管音频 |
| Domain | `experience.py` | 新增 | `InputMode/QualityTier/VoiceStyle/StageState`值对象与不变量 |
| Domain | `source_pack.py` | 新增 | V2-X manifest结构；不定义多Character聚合 |
| Ports | `ExperienceManifestRepository` | 新增 | load/stage/commit/rollback，隐藏文件系统锁与路径 |
| Ports | `VisualDescriptionPort` | 新增 | 本地候选描述；返回provenance，禁止直接写记忆 |
| Infrastructure | `JsonManifestRepository` | 新增 | 同目录临时文件+fsync+原子替换；严格根路径解析和schema校验 |
| Infrastructure | `SqliteMemoryRepository` | 修改 | 派生分组/边事务和删除传播；原记忆仍为权威 |

## 3. Manifest v1

私有根目录下使用`v2x/manifests/source-pack.v1.json`，不进入Git：

```json
{
  "schema_version": 1,
  "pack_id": "uuid",
  "revision": 1,
  "active_appearance_id": "uuid-or-null",
  "active_scene_id": "uuid-or-null",
  "sources": [{
    "source_id": "uuid",
    "sha256": "64hex",
    "relative_path": "v2x/sources/<uuid>.<ext>",
    "angle": "front|left|right|full_body|unknown",
    "appearance_label": "user text",
    "consent_id": "local consent id",
    "provenance": "upload",
    "created_at": "RFC3339"
  }],
  "appearances": [{"appearance_id":"uuid","source_ids":["uuid"],"confirmed":true}],
  "scenes": [{"scene_id":"uuid","label":"user text","asset_sha256":"64hex"}],
  "renditions": [{"rendition_id":"uuid","kind":"idle|micro_action|talking","source_ids":["uuid"],"scene_id":"uuid","status":"staged|approved|active|rejected","sha256":"64hex"}]
}
```

规则：ID创建后不可变；`revision`严格+1；路径只允许服务端生成的相对路径；原图只读；派生物写到staging，哈希、媒体探针和人工批准通过后才进入manifest；active切换以单个原子manifest提交完成。

## 4. 设置与Feature Flag

配置键统一以`v2x.`开头：`contracts`、`input_calibration`、`lifecycle_recovery`、`output_controls`、`pwa`、`source_pack`、`stage_composition`、`scene_presets`、`micro_actions`、`visual_claims`、`memory_workbench`、`hd_talking`、`quality_governor`、`voice_styles`。默认仅`contracts=true`，其余在各子阶段验收后逐项开启。关闭任一键必须恢复对应V1行为，不删除新数据。

## 5. 输入状态机与事件

`stopped → starting → calibrating? → listening ↔ capturing → recovering → listening|error`。

- `InputCalibration`只保存设备ID哈希、噪声RMS分位数、阈值、时间和算法版本，不保存音频。
- 自动阈值限制在安全上下界；播放态打断另有更高阈值、最小时长和迟滞。
- PTT模式只有按键按下期间可启动utterance；释放后走正常hangover，不改变后端ASR权威。
- `input.device.changed`先停旧track和AudioContext，再启动新设备；失败恢复default且活动track≤1。

## 6. 生命周期合同

`SessionLifecycleController`持有单调递增`lifecycleGeneration`。visibility恢复、网络恢复、health恢复都进入同一串行队列：停止旧输入/输出/avatar句柄→探测Gateway→恢复同一有效session或显式回Idle→创建一套资源。所有异步回调必须校验generation；旧generation的音频、视频、重连和UI状态全部丢弃。

## 7. 输出与A/V质量合同

- `MediaSession`的链路为`source → GainNode → DynamicsCompressorNode → meter → destination`；默认gain=1，压缩可关闭。
- 只在内存保留“当前回答”PCM块，收到新turn、打断、结束会话或页面卸载即清除。
- `setSinkId`只在浏览器支持时显示；不支持时返回明确`unsupported`，不能报成功。
- 质量采样：视频帧年龄、decoder backlog、30秒冻结率、音频时钟与最近视频时间差。升级/降级均要求连续窗口与冷却期，防抖动；降级顺序为丢过期帧→降低视频质量→Idle/静态回退，音频不断流。

## 8. 舞台与微动作状态机

`intro → idle → listening_cue → thinking_cue → pre_speech → live_talking → recovery_cue → idle → outro`。任何时刻仅一个可见人物表面。微动作不得覆盖`live_talking` Canvas、不得持有音频时钟；缺少对应素材、`prefers-reduced-motion`或质量降级时直接使用approved低幅Idle/静态图。场景和人物机位必须由同一rendition revision绑定。

## 9. 视觉声明与记忆图

`VisualClaim`状态为`candidate|confirmed|rejected|superseded`，记录claim、source_ids、模型/提示版本、时间和用户事件。只有confirmed可进入PromptCompiler；身体、身份、健康等敏感推断禁止生成候选。MemoryGraph只从memory id派生，节点/边必须带source_memory_ids；编辑触发重建，删除在同一事务删除相关节点/边/FTS/vector，验收查询零召回。

## 10. API增量

| 方法/路径 | 用途 | 失败语义 |
|---|---|---|
| GET/PUT `/api/v1/experience/settings` | flag与安全偏好 | 版本冲突409；非法组合422 |
| POST `/api/v1/input/calibrations` | 写入无音频校准摘要 | 无样本/越界422；不写部分结果 |
| GET `/api/v1/devices/capabilities` | 浏览器能力提示的服务端策略 | 不宣称浏览器实际支持 |
| GET/POST `/api/v1/source-pack` | 读取/创建活动角色manifest | schema/授权/配额失败保持旧revision |
| POST `/api/v1/source-pack/sources` | 多文件逐项staging | 单文件失败不激活整包 |
| POST `/api/v1/stage/activate` | 原子切appearance/scene/rendition | 资源未ready为409，旧舞台不变 |
| GET/POST `/api/v1/visual-claims` | 候选列表与确认/拒绝 | 未确认不可注入对话 |
| GET `/api/v1/memory-graph` | 只读派生图 | 返回source ids；不可写 |
| GET `/api/v1/quality` | 当前档位与脱敏指标 | 无私密正文/媒体字段 |

所有响应沿用V1错误envelope和loopback限制。新增WS事件使用现有6字段envelope：`lifecycle.recovering/recovered`、`quality.changed`、`stage.changed`；事件必须带generation/revision且服从现有event_seq丢旧规则。

## 11. 迁移与回滚

1. X0只建立基线、flag、manifest schema验证和dry-run，不改变active资产。
2. 首次启用source-pack时，从V1 active portrait创建一个稳定pack/source UUID并记录旧asset id；重复运行返回同一ID。
3. manifest提交前保存上一revision及SHA-256；失败或关闭flag时继续解析V1 active asset。
4. SQLite增量使用新迁移文件，不改写`0001_init.sql`；迁移事务、重复执行和备份恢复都必须测试。
5. 每一工作包独立flag；回滚只关对应flag并恢复上一active revision，保留staging供诊断，不覆盖原图。

## 12. 证据合同

合同测试可用合成数据；功能出门必须使用授权本机素材、真实浏览器、真实音频/模型或明确故障注入。自动指标可签结构、性能、资源和泄漏门；Idle/微动作自然度、身份保持、声音自然度和口型自然度仍需人工盲评。报告只保存哈希、计数、时间、状态和脱敏截图，不保存私人原图、原音频、记忆正文或完整对话。
