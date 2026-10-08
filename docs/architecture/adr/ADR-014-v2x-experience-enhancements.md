# ADR-014：V2-X体验增强采用模块化单体兼容扩展

**状态**：Accepted for implementation after D1 gate  
**日期**：2026-10-08

## 背景

V2-X需要同时改善设备输入、生命周期、音频控制、桌面沉浸、多源素材、舞台、微动作、视觉确认、记忆工作台、高清口型和声音风格，但必须保留V1已通过的实时链、16GB空闲内存边界、离线隐私和单人物表现。

## 备选路线

### A. 在现有模块化单体中按能力扩展（采用）

复用Gateway和现有前端会话服务，新能力以application service、port和独立前端controller加入；文件manifest承担V2-X素材聚合，SQLite承担用户确认和派生记忆索引。

优点：迁移小、逐项flag回退、不会改变部署拓扑；V2-A可登记现有稳定ID。缺点：需要严格阻止`App.tsx`继续膨胀，文件manifest与SQLite之间必须有明确权威边界。

### B. 立即迁移V2-A完整领域模型

现在就引入Character/Space/Appearance聚合、插件宿主和导入导出。

优点：长期模型一步到位。缺点：数据库、路径、导航和活动上下文同时变化，难以区分体验问题与迁移问题，回滚半径大；违反已批准的X→A顺序。拒绝。

### C. 独立微服务/Python worker承载每项体验能力

优点：进程隔离清晰。缺点：增加端口、生命周期、内存和恢复复杂度，在单机资源预算内性价比差；大部分能力并不需要隔离。拒绝，只有未来不可信插件宿主允许独立进程。

## 决策

采用A。实时音频/视频继续走既有WS与generation fence；控制与manifest走loopback REST。新增UI逻辑从`App.tsx`拆到feature组件和controller。V2-X只有一个活动角色，manifest中的UUID是未来V2-A迁移锚点，不是提前开放多角色。

素材权威为原图+版本化manifest；记忆权威仍是SQLite memories，关系图只是可重建派生物；未确认视觉描述不是事实。PWA只缓存版本化静态壳，私有数据全部`no-store`。

## 影响

- 正向：各能力可独立发布/回退；V1链的故障域不扩大；硬件预算可按阶段测量。
- 代价：新增manifest事务实现、schema验证和跨介质一致性测试；前端需拆分会话外能力。
- 风险：manifest与active V1资产漂移。通过单一`SourcePackService`提交、revision CAS和回滚指针关闭。
- 风险：质量治理频繁切档。通过连续窗口、迟滞、冷却期和音频优先关闭。
- 风险：视觉推断固化错误。通过candidate→人类确认→可注入三段式关闭。

## 回滚

每项能力使用独立`v2x.*` flag。关闭后恢复V1输入、活动资产、Idle/live状态和默认声音路径；新增数据保留但不可被运行态读取。数据库迁移仅新增表/索引，manifest保留前一revision；回滚不得删除原图或重写UUID。

## 验证

以`V2-development-plan.md`的AC01～15、D1实现合同和`v2-x-gap.drawio`为准。任何V1首响/打断/资源/隐私回退、双人物、未确认事实固化或旧generation复活均停线。
