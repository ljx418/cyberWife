# V2-X3.3 预开发内部审计

## 审计结论

**PASS，可进入实现；P0/P1未闭环风险为0。**

## 风险闭环

| 风险 | 原始等级 | 闭环措施 | 残余等级 |
|---|---:|---|---:|
| 静态背景切换后说话回到旧客厅 | P0 | 场景没有同背景Wav2Lip数据集时`can_activate=false`；Idle/talking成对登记 | 低 |
| 切换时出现两个女人或遮罩层 | P0 | 只使用完整场景视频和完整场景Wav2Lip帧；`matting=false`，单Canvas | 低 |
| 安装半成功污染活动状态 | P1 | 文件先落不可引用位置并校验；绑定清单与SourcePack批准记录完成后才可激活 | 低 |
| 并发激活覆盖用户选择 | P1 | 客户端必须提交`expected_revision`；JsonManifestRepository锁内CAS | 低 |
| 对话中切换导致音画错配 | P1 | 只允许Idle/聆听态切换；会话WS不动，Avatar以目标ID重连，同场景Idle托底 | 中低 |
| 刷新后前端回到默认场景 | P1 | 启动时读取活动场景和活动Avatar绑定，不依赖localStorage作为权威 | 低 |
| 私有视频被Service Worker缓存 | P1 | 私有Idle走`/api/`且`Cache-Control:no-store, private`；既有SW拒绝API缓存 | 低 |
| 资源突破本机预算 | P1 | 三个Wav2Lip数据集离线串行构建；不加载Qwen/Wan；运行时仍只加载一个Avatar | 低 |

## 架构一致性

- 复用现有`AvatarSession.start(canvas, avatar_id)`动态加载能力和单Canvas舞台，不改变A/V同步时钟。
- SourcePack保存可迁移稳定ID、rendition状态和SHA；V2-X私有绑定保存本机运行引用，V2-A可登记迁移而无需重生成ID。
- 不修改ConversationOrchestrator、TTS、ASR、LLM或记忆边界。

## 进入实现条件

X3.2已由项目所有者批准；四份开发前文档齐全；没有新增致命或重大规格偏差。允许进入实质开发。
