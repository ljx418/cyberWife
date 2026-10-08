# V2-X-D1 内部风险闭环

**日期**：2026-10-08  
**方法**：按需求覆盖、代码事实、依赖方向、状态/失败语义、数据迁移、资源隐私六个视角独立检查。  
**结论**：PASS；开放Critical/P0/P1=0。

## 第一轮：规格到实现

| 范围 | 责任实体 | 验收 | 结论 |
|---|---|---|---|
| R01极端窗口/背景 | StageControls、StagePresentationController、ScenePresetService | AC02/03 | 覆盖 |
| R02～03身材穿着/多源图 | SourcePackPanel、SourcePackService、VisualClaimService | AC01/05 | 覆盖；只允许用户确认描述 |
| R04 Idle | StagePresentationController、rendition manifest | AC04 | 覆盖；人工自然度不由机器代签 |
| R05多形象/空间/导入导出 | V2-A | V2A-AC01～04 | 已明确排除V2-X，没有假入口 |
| R06记忆/图谱/插件 | MemoryWorkbench、MemoryGraphService；插件在V2-A | AC06/V2A-AC05～07 | 权威/派生边界明确 |
| R07高清口型 | AvatarSession、QualityGovernor、候选模型离线串行 | AC08/13 | 覆盖；不能插值冒充 |
| R08输入鲁棒性 | InputAudioSession、DevicePanel | AC09 | 覆盖 |
| R09生命周期 | SessionLifecycleController | AC10 | 覆盖 |
| R10输出控制 | MediaSession、OutputControls | AC11 | 覆盖 |
| R11微动作 | StagePresentationController | AC12 | 覆盖 |
| R12质量治理 | AvatarSession、QualityGovernor | AC13 | 覆盖 |
| R13声音风格 | VoiceStylePolicy | AC14 | 覆盖 |
| R14桌面沉浸 | PwaBridge、HostBridge | AC15 | 覆盖 |

发现并关闭：原合同只在总计划中映射R/AC，D1实现合同没有重复整张追踪表。为避免双重权威，保留总计划为唯一详细需求矩阵，并在本审计记录责任实体；不是缺口。

## 第二轮：当前代码事实与依赖

- 已逐文件确认`InputAudioSessionController`、`MediaSession`、`AvatarSessionController`、`ConversationClient`、`TurnPipeline`、`SessionRuntime`、`MemoryService`、`AssetStore`和`SqliteMemoryRepository`存在。
- 计划新增实体均标为“新增”，没有把D0原型组件误报为已实现。
- API只调用application；application依赖domain/ports；infrastructure实现port。没有要求domain导入React、FastAPI、SQLite或MCP SDK。
- `App.tsx`现有职责偏重列为修改项，D1禁止继续堆领域逻辑。

结论：PASS，无架构事实虚构或逆向依赖P1。

## 第三轮：状态、失败与迁移

- 输入、生命周期、舞台、视觉声明均有显式状态；旧异步回调以generation丢弃。
- manifest采用staging、校验、revision CAS和原子替换；失败保留上一active。
- V1 active asset在迁移未通过前仍为事实源；首次映射幂等且UUID不重写。
- MemoryGraph是派生视图；编辑重建、删除同事务传播；原记忆/FTS/vector/图必须零残留。

发现并关闭：如果manifest与V1 active asset同时写会产生双权威。合同已规定切换前V1权威、相应子阶段验收后manifest权威，写入只能由`SourcePackService`提交。

## 第四轮：资源、隐私和真实性

- 生成与实时模型串行、RAM/VRAM及2GB余量硬门均保留。
- Service Worker只缓存内容哈希静态壳；API/WS/私有媒体network-only/no-store。
- 校准只保存统计摘要；重播只在内存；报告不保存对话/音频/记忆正文。
- 真实浏览器、真实素材/音频/模型和故障注入才能签功能门；主观质量保留人工盲评。

结论：PASS，无隐私、资源或虚假验收P0/P1。

## 开放P2

| 风险 | 触发 | 责任阶段 | 回退 |
|---|---|---|---|
| 浏览器不支持sink/PWA安装 | 能力检测为false | X0.3/X9 | 隐藏设备选择/保留普通浏览器入口 |
| 文件系统原子替换语义差异 | WSL/NTFS故障注入失败 | X0 | manifest留在ext4私有数据根；关闭source_pack flag |
| 低幅微动作素材主观不自然 | 人工评分&lt;4 | X4 | 退回approved Idle，不影响实时口型 |

以上均有明确阶段和安全回退，不阻断D1出门。
