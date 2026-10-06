# cyberWife V1～V2 项目里程碑与交付计划

**版本**：3.4
**日期**：2026-10-06

**状态**：B0～B5、B2.5、ARCH1、RES1、V1RC1及UX10自动化门完成；V1FINAL现场门待结构化报告，新Idle候选待人工决定是否激活；部署最低门为INST1-AC07单机隔离可移植性
**详细任务**：[`backend-development-plan.md`](backend-development-plan.md)

## 1. 项目现状

前端既有主交互已被用户确认为满足 V1，六态、主操作和对话链继续受G-UX保护；项目所有者于2026-10-06批准极端窗口、背景、Idle、记忆工作台等定向体验优化，并批准V2按体验交互优化→架构扩容执行。仓库已有领域对象、SQLite 基础、Gateway REST 骨架、六态状态机、VAD/ASR/LLM/Qwen/CosyVoice 适配器、Avatar 上游代码以及 PowerShell 启动脚本；这些是可复用基础，不是V2新增能力的完成证据。

V1核心功能已完成开发并取得目标硬件真实证据。B2以本机H.264 WebSocket/WebCodecs完成故障恢复，B3/B4/B5完成打断、记忆隐私、组合回归和发布冻结。UX5/ARCH1/RES1已关闭A/V机器量化、架构分层和AC-14资源红项；V1RC1又以当前代码重跑普通链、打断与60分钟组合。V1FINAL把原纯人工签字脚本升级为不保存正文/音频的headed Chrome机器取证器；INST1-AC06R已消除硬编码工件依赖。因所有者只有一台电脑，ADR-012新增AC07，以同机隔离venv、离线wheelhouse、替代数据根、便携制品和真实生命周期证明有限可移植性；AC06独立新环境降为增强项。商业发布继续被Wav2Lip ResearchOnly阻断。

## 2. 固定边界

- 硬件：Windows 11、32GB物理RAM、空闲约16GB可用、RTX 4090 24GB；VRAM≤22GB，项目非可回收RAM≤14GB，宿主/WSL可用内存均≥2GB。
- 部署：Windows + WSL2 本机原生进程；V1 不引入 Docker。
- 网络：仅 loopback/当次Windows↔WSL本机桥接；核心体验不得依赖公网。物理断网会中断宿主终端，按用户决议改用白盒出站审查与运行期连接采样。
- 数据：原始麦克风音频不落盘；转录 30 天；长期记忆保留至用户删除。
- 模型：非 TensorRT CosyVoice2 为 V1 默认；Qwen3-TTS 保留为显式回退，不双常驻。
- 前端：V1主交互和六态保持稳定；只实施已批准的定向体验工作包，任何新增路由/组件必须绑定V1修补或V2-X/V2-A需求与验收ID。

## 3. 总体依赖

```text
G-UX + DOC-B 已批准
  └─ B0 PASS：可运行基线/启动/真实健康
      └─ B1 PASS：真实输入/ASR/LLM TurnPipeline
          └─ B2.5 PASS：首响/缓存/授权盲听
              └─ B2 PASS：H.264 Avatar故障降级与原页恢复
                  └─ B3 PASS：统一打断/无限多轮稳定性
                      └─ B4 PASS：记忆/隐私/保留
                          └─ B5 PASS：故障、离线、一键生命周期与 V1 总验收
```

B2.5名称保留但不按编号机械排队；它是已完成的B2性能修复分支。工程阶段门均已按依赖顺序执行；这不自动等同于最终产品门全绿。

## 4. 里程碑总览

| 阶段 | 用户可感知结果 | 关键代码实体 | 入口门 | 出门门 |
|---|---|---|---|---|
| DOC-B | 可以判断怎么开发、怎么失败、怎么验收 | PRD/架构/计划/Draw.io | G-UX 通过 | 文档内审通过 + 人类批准方向 |
| B0 | 一个命令可靠启动并显示真实状态 | Launcher、Gateway、Health、ModelRegistry | 开发授权 | 幂等启动/停止；四进程真实 probe |
| B1 | 说话后得到真实字幕和角色文本 | SpeechRuntime、TurnPipeline、WS | B0 Pass | 20 轮≥95%；事件不串轮 |
| B2 | 听到克隆声音并看到同步人物 | QwenTtsAdapter、LiveTalkingAdapter | B1 Pass | 首响/FPS/资源/降级达门 |
| B2.5 | 普通回答更快、问候可安全预热且随时可回退 | RuntimeMetrics、加速profile、WarmResponseCache | B2首响阻断 + G-OX批准 | OX-01～05、07、08、10～12 Pass |
| B3 | 可随时打断并长期多轮稳定 | InterruptionController、CancellationToken | B2 Pass | 打断 P95≤400ms；1h 稳态 |
| B4 | 记忆可查改删且支持不记录 | MemoryService、RetentionService、Repository | B3 Pass | 删除0召回；不记录0写入 |
| B5 | 本机边界、一键、故障恢复后形成候选版 | 所有后端实体、验收工具 | B3+B4 Pass | AC-01～14 全 Pass；P0/P1=0 |
| UX4 | 用户在引导内把照片稳定生成并启用为动态人物 | AvatarAssetService、avatar_idle_pipeline、Onboarding | 三张工作流样片获人工批准 | UX4-AC01～08 Pass；未确认不替换；四服务恢复 |
| UX8 | 普通话字幕不再保留粤语特有词形，句中自然停顿不被过早截断 | MandarinTranscriptNormalizer、UtteranceBoundaryDetector | 用户真实交互反馈 | UX8-AC01～06机器PASS；AC07物理麦克风待签 |
| UX10 | 极端窗口无空白、背景可切换、Idle低动作候选与记忆新增/确认可用 | App布局、MemoryService、avatar_idle_pipeline | V1人工反馈及G-V2定向授权 | 自动化PASS；新Idle不自动激活，现场自然度待签 |
| V1FINAL | 人只做听感/说话，机器绑定现场三轮、打断、接续、人物与Idle证据；部署证明采用显式保证等级 | Invoke-ACC1HumanGate、Invoke-INST1SingleMachinePortability、audit_v1_completion | V1RC1自动化PASS | VF-AC01～09；AC07为V1最低门，AC06为增强项 |

## 5. 每阶段交付包

每个里程碑必须同时交付以下内容，缺一不可：

1. 对应代码和配置；
2. 单元、合同和集成测试；
3. 目标硬件上的真实模型 smoke；
4. 机器可读结果（JUnit/JSON/CSV）；
5. 人类可复核的脱敏日志、截图或视频；
6. 里程碑审计文档，逐条对照入口、任务和出门门槛；
7. 更新后的需求追踪矩阵和已知限制。

B3、B4、B5及V1FINAL的计划、验收、审计与PRD复核分别位于`docs/stages/`；历史开发前状态不代表当前状态，当前候选以V1RC1冻结和V1FINAL结果为准。

## 6. 模型决策门

### Qwen 回退轨

Qwen3-TTS 已有固定样本 CER=0% 的内容正确性证据，按 ADR-008 保留为显式回退。其全链尾延迟不满足当前默认轨，不能伪报为默认。

### CosyVoice 候选轨

CosyVoice2 已用正确参考逐字稿完成30条复测：CER=0.71%。V1RC1修复冻结上游流式hop窗口跨请求增长并加入系统余量/Gateway RSS双回收门后，Windows Chrome普通链30/30、P50/P95=4.102/4.708秒；同候选60分钟RAM/VRAM/趋势全部达门。ADR-008默认非TensorRT CosyVoice不变，Qwen保留显式回退。

### B2.5 优化轨

先统一浏览器端首响分段计量，再按“llama.cpp低风险调优→CosyVoice TensorRT验证→ASR ext4稳定化”的顺序逐级验证。TensorRT已因尾延迟回退被拒绝；用户批准P95≤7秒后，条件LLM运行时迁移取消，达门即停止扩大复杂度。严格问候预热最多6项、内存≤64MiB、完整版本键失效；命中结果独立统计，不能用于普通路径出门。详细计划见 [`stages/B2.5/plan.md`](stages/B2.5/plan.md)。

## 7. 验收与缺陷门

- P0：隐私泄漏、越过授权、不可恢复数据破坏。发现即停线。
- P1：主链不可用、崩溃/OOM、删除仍召回、出现公网依赖/联网上传动作、首响/打断/FPS未达标。不得进入下一阶段。
- P2：存在明确绕行的局部问题。只有用户书面接受才可带入 V1。
- Mock 只证明合同，不证明出门；真实模型与目标硬件证据是 B0～B5 及 B2.5 的硬要求。
- 所有门槛以 [`acceptance-plan.md`](acceptance-plan.md) 和 [`stages/B2.5/acceptance.md`](stages/B2.5/acceptance.md) 为准，不得在实现中下调。

## 8. V1 完成定义

用户从干净启动状态执行一个入口即可完成自检、打开已批准的陪伴页面并开始连续语音对话；至少 20 轮成功率≥95%，可以在 P95 400ms 内打断，普通链首响P95≤7.0s（P50报告），数字人≥25FPS，运行 1 小时无崩溃/OOM/延迟积累；核心链无公网依赖或联网上传动作，记忆可彻底删除，不记录会话零持久化，退出后无残留进程与临时音频。

V1 Go 需要 AC-01～AC-14 全部通过、开放 P0/P1=0，并完成安装、启动、备份、恢复、卸载和数据清除演练。部署至少通过AC07单机隔离可移植性，报告不得声称跨机器/驱动兼容；AC06独立干净机为增强保证。真实读屏/麦克风现场报告仍必须闭环。

## 9. V1 后续体验修补与 V2 阶段

V1人工总验收前四项低风险修补已由UX10实现并通过自动化：极端窗口布局、本地背景库、低幅Idle候选、记忆手工新增/候选确认。低动作候选仍受人工批准门保护，当前active不会被自动替换。UX10的完成不提前解锁V2-X实际开发；仍先执行V1现场总验收。

V2 已由项目所有者批准拆成两个顺序阶段：

| 阶段 | 用户可感知结果 | 架构边界 | 出门门 |
|---|---|---|---|
| V2-X 体验交互优化（先执行） | 多源照片、头像/半身/全身构图、外观与背景预设、低幅Idle、可确认的图像描述、可视化记忆工作台 | 仍为一个活动角色；所有新增素材用稳定ID和版本化清单，为迁移预留边界 | V2X-AC01～07全PASS；V1门无回退；P0/P1=0 |
| V2-A 架构扩容（后执行） | 多形象、多空间、文件隔离、导入导出、图谱聚类、MCP/RAG/CLI记忆连接器 | 模块化单体新增Character/Appearance/Space/Memory bounded context；只隔离不可信插件宿主 | V2A-AC01～07全PASS；迁移可回滚；串数据/越权为0 |

详细任务、顺序、验收和停线条件以 [`V2-development-plan.md`](V2-development-plan.md) 为准；架构决策见 [`ADR-013`](architecture/adr/ADR-013-v2-experience-first-expansion.md)。Docker/Compose由ADR-007保留为独立部署轨，不得阻塞V2-X体验开发，也不得默认成为V2-A本机运行前置条件。公网访问、多用户、云同步与商业发布仍不在已批准V2范围内。
