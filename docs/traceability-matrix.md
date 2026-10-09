# cyberWife V1 需求追踪矩阵

**版本**：3.4　**日期**：2026-10-07
用途：确保已批准体验、实现实体与 AC-01～14/AC-04A/UX13/UX14/UX15 不发生偏移。当前运行态视觉结论以 `stages/UX15/result.md` 为准；UX11抠图路线仅保留历史与回退语境，UX12是直接生成研究基线。

## 功能需求

| 需求 | 后端实现实体 | 里程碑 | 验收 | 当前状态 |
|---|---|---|---|---|
| FR-01 五步设置/续接 | ApiGateway、SqliteRepository、OnboardingDraft | B0/B5 | AC-01 | 已实现并验收：真实五步5/5、草稿续接与发布浏览器授权门PASS |
| FR-02 授权/撤销 | Consent domain、Repository、AssetStore | B4/B5 | AC-01/02 | 已实现并验收：授予/撤销、未授权403、active pointer停用PASS |
| FR-03 真实运行检查 | HealthAggregator、ModelRegistry、probe ports | B0/B2.5 | AC-12 | 已实现并验收：六组件状态来自真实功能探针，12/12故障恢复PASS |
| FR-04 人物资产 | AssetStore、AssetRepository | B0/B5 | AC-02 | 已实现并验收：版本、预览、原子激活、失败回滚与恢复上一版PASS |
| FR-05 声音资产/试听 | AssetStore、CosyVoiceAdapter、QwenTtsAdapter | B0/B2 | AC-02 | 已实现并验收：授权声音真实Cosy试听、版本切换、Qwen显式回退PASS |
| FR-06 人设持久化 | Profile domain、SqliteRepository、PromptCompiler | B0/B1 | AC-01/11 | 已实现并验收：完整字段、乐观并发409、历史快照和重启一致PASS |
| FR-07 六态状态机 | ConversationOrchestrator、TurnPipeline | B1/B3 | AC-03/11 | 已实现并验收：真实事件链、状态播报与打断状态转换PASS |
| FR-08 连续对话 | ApiGateway、SpeechRuntime、TurnPipeline、MandarinTranscriptNormalizer、UtteranceBoundaryDetector、各 adapter | B1/B2/B2.5/B3/UX8/V1FINAL | AC-03/04/UX8-AC01～07/VF-AC03 | 主链已验收：20/20连续链、普通链30/30、60分钟组合及项目所有者物理麦克风人工总验收PASS |
| FR-09 插话取消 | InterruptionController、CancellationToken | B3 | AC-05 | 已实现并验收：早/中/晚30/30，旧generation零泄漏PASS |
| FR-10 口型/静态降级 | LiveTalkingAdapter、H264WebSocketOutput、BaseASR实时抖动缓冲、AvatarSession、AvatarAssetService、build_video_avatar(scenev1/scenev2)、manifest融合profile、App双缓冲单表面状态机 | B2/UX5/UX6/UX13/UX14/UX15/V1FINAL/V2-X3.3-R1/V2-X8.0 | AC-06/AC-06A/UX14单表面门/UX15连续性门/VF-AC05/06/R1-AC01～07/V2X8.0-AC01～06 | V1同一完整场景人物与无闪动门PASS；R1四场景自动门和人工A/B均PASS并已激活scenev2；整脸回贴同输入实测边界和锐度劣化，未激活；MuseTalk 1.5进入串行候选验证，高清/音素自然度仍由V2-X8承担 |
| FR-11 设置持久化 | Gateway application services、repositories | B0/B4/B5 | AC-01/02/08 | 已实现并验收：六页签真实API与跨重启持久化PASS |
| FR-12 记忆 CRUD/来源 | MemoryService、SqliteMemoryRepository、VectorIndex | B4/UX10 | AC-07/08/UX10-AC05～07 | 已实现并验收：真实手工新增/编辑/删除；语音会话候选确认前0召回、确认后命中、重复确认幂等、删除后0命中 |
| FR-13 本次不记录 | TurnPipeline、persistence policy | B4 | AC-09 | 已实现并验收：会话中启用后整场业务写入0，原始音频0落盘PASS |
| FR-14 30天清理 | RetentionService、injectable clock | B4 | AC-10 | 已实现并验收：可注入时钟、转录到期清理且长期记忆保留PASS |
| FR-15 单服务恢复 | HealthAggregator、RuntimeLauncher、adapters | B0/B2/B2.5/B5 | AC-12 | 已实现并验收：四组件×3恢复、同页继续及Avatar单项恢复PASS |
| FR-16 响应式/无障碍 | App宽高比舞台 + 后端真实状态事件 | B5/UX10/ACC1/V1FINAL | AC-11/UX10-AC01/08/VF-AC06 | 含2160×3500/3840×180的五类视口、24/24 Playwright、axe/焦点/aria-live/reduced-motion与项目所有者人工总验收PASS |
| FR-17 一键生命周期 | Install-CyberWife.ps1、prepare_local_artifacts.py、RuntimeLauncher.ps1、Invoke-INST1SingleMachinePortability.ps1；AC06为增强项 | B0/B5/INST1 | AC-14/G6/INST1-AC07 | RES1与目标机生命周期PASS；AC07复核隔离venv、no-index wheelhouse、替代数据根、便携制品和真实生命周期，并披露同机限制 |
| FR-18 本机边界/无公网依赖 | Launcher、Gateway、所有 adapters | B0/B2/B2.5/B5 | AC-13/OX-10 | 已实现并验收：仅loopback/本机桥接、出站白盒与连续连接采样PASS；物理断网按用户决议不执行 |
| FR-19 HostBridge | browser HostBridge | B5 | 合同回归 | 已实现并验收：浏览器安全unsupported空操作，无本机越权PASS |
| FR-20 严格问候预热 | WarmResponsePolicy、WarmResponseCache、RuntimeMetrics | B2.5 | AC-04A/OX-03～05 | 已开发并签署；真实命中P95=56ms、30条负例错误命中=0 |

## 非功能需求

| 需求 | 实现实体 | 里程碑 | 验收 | 当前状态 |
|---|---|---|---|---|
| NFR-01 首响/打断 | TurnPipeline、InterruptionController、RuntimeMetrics | B2/B2.5/B3/V1RC1 | AC-04/04A/05 | 当前候选已验收：普通30轮P50/P95=4.102/4.708s；缓存历史P95=14ms；打断30轮P95=1.9ms |
| NFR-02 FPS/资源 | Scheduler、AvatarAdapter、RuntimeMetrics | B2/B2.5/B5/V1RC1 | AC-04/06/14 | 当前候选PASS：60分钟RAM峰值13,775.637MiB、GPU 11.219GiB、Windows/WSL最低6,181.547/8,989.289MiB；Avatar协议v2、89,981帧 |
| NFR-03 稳定性 | 有界队列、Launcher、Health | B3/B5/RES1 | AC-03/12/14 | 已验收：60分钟20完整+10打断、资源与趋势门、恢复、stop×2均PASS |
| NFR-04 本机隐私 | persistence policy、loopback、privacy scan | B4/B5 | AC-09/13 | 已验收：原始音频/允许集外连接/敏感日志命中均0 |
| NFR-05 删除一致性 | MemoryService、SQLite transaction | B4 | AC-08 | 已验收：源记录、FTS、向量与召回原子归零PASS |
| NFR-06 可观测/脱敏 | StructuredLogger、RuntimeMetrics、audit_v1_completion | B1/B2.5/B5/V1FINAL | AC-04/12/13/VF-AC09 | trace/generation/分段计量与日志脱敏PASS；最终总门逐文件复算发布SHA，只输出状态码，不复制私人报告正文 |
| NFR-07 分层/替换 | ports/adapters、contract tests | B0～B5/ARCH1 | 架构审查 | 已验收：Application反向导入=0并有AST门禁；具体实现仅由组合根注入 |
| NFR-08 可访问性 | 已批准前端、真实 aria-live 事件 | B5/UX10/ACC1/V1FINAL | AC-11/UX10-AC08/VF-AC06 | 键盘旅程、当前Playwright 24/24与项目所有者人工总验收PASS |
| NFR-09 磁盘 | HealthAggregator、RetentionService | B0/B4 | AC-10/12 | 已验收：低水位禁止缓存、保留清理和数据生命周期PASS |
| NFR-10 许可证 | ModelRegistry、release manifest | B0/B5/UX4 | 发布审查 | 7个实时模型hash/来源/许可证冻结；10个离线形象模型纳入ComfyUI保留索引与安装前检；商业用途因Wav2Lip为No-Go |

## 完整性规则

1. 每个 Must 需求必须同时有代码实体、里程碑、可执行 AC 和真实证据。
2. “文件存在”“mock 通过”“端口监听”不能把状态提升为“已验收”。
3. 前端体验已冻结，不等于后端事件接线后的 AC-11 自动通过。
4. CosyVoice已由ADR-008切为默认非TensorRT profile；Qwen adapter与显式profile必须保留到V1总验收完成。
5. 发布前所有行必须为“已实现并验收”，证据路径进入 V1 总报告。
6. 按ADR-009顺序执行：B2.5首响/缓存→B2 Avatar恢复→B3打断→B4记忆隐私→B5完整组合回归；缓存命中不得混入普通首响统计。
7. B3—B5 可执行命令、退出码和证据目录以 [`acceptance-command-manifest.md`](acceptance-command-manifest.md) v1.2 为准；当前工程候选基线为2026-10-06 V1RC1，外部门以V1FINAL为准。

## AC → FR 反向索引

| AC | 覆盖 FR |
|---|---|
| AC-01 | FR-01、FR-02、FR-06 |
| AC-02 | FR-02、FR-04、FR-05、FR-11 |
| AC-03 | FR-07、FR-08 |
| AC-04 / AC-04A | FR-08、FR-20 |
| AC-05 | FR-09 |
| AC-06 | FR-10 |
| AC-07 | FR-12 |
| AC-08 | FR-11、FR-12 |
| AC-09 | FR-13 |
| AC-10 | FR-14 |
| AC-11 | FR-07、FR-16、FR-19 |
| AC-12 | FR-03、FR-15 |
| AC-13 | FR-02、FR-13、FR-18、FR-20 |
| AC-14 | FR-08、FR-17 |
