# cyberWife V1～V2 全局开发状态

**快照日期**：2026-10-07（V1自动化、项目所有者人工总验收、同revision发布/AC07/总门聚合全部通过）

**判定口径**：按阶段出门门禁，不按代码文件数量或局部测试数量

## 1. 结论

原B0～B5六个开发阶段加B2.5共七个工程阶段门：**7/7已有实现与目标机证据**。UX10～UX15关闭极端窗口、背景、记忆操作、完整场景Idle、单一人物说话表面与启停连续性缺口。V1RC1普通Chrome链30/30、P50/P95=4.102/4.708秒；打断30/30、静音P95=1.9ms；60分钟20完整+10打断全PASS。项目所有者已完成并确认V1人工总验收PASS。用户批准以INST1-AC07单机隔离可移植性替代第二台物理机硬门；AC06保留为增强项。商业用途因Wav2Lip ResearchOnly为NO-GO。

## 2. 分阶段状态

| 阶段 | 当前状态 | 已有真实证据 | 仍缺内容 |
|---|---|---|---|
| G-UX / DOC-B | PASS | 前端方向已批准；Playwright 24/24；最终人工路径已获项目所有者PASS | 无 |
| B0 | PASS | 幂等生命周期、六组件真实probe | 无 |
| B1 | PASS | 真实PCM→VAD→ASR→LLM 20/20 | 无 |
| B2 | PASS | H.264/WebCodecs双FPS≥25、故障降级与原页恢复；实时PCM抖动修复后当前人物嘴部响应4/4；人工总验收PASS | 高清、同步与嘴部自然度提升转V2-X8 |
| B2.5 | PASS | Cosy普通链P95≤7s、严格缓存、授权盲听、回退 | 无 |
| B3 | PASS（授权音频） | 30次真实打断、旧轮零泄漏、压力证据 | 真实物理麦克风自由对话未自动化覆盖 |
| B4 | PASS | sqlite-vec、删除事务、no-record、30天保留 | 无 |
| B5 / V1RC1 | PASS（私人研究V1） | 当前候选普通链30/30、打断30/30、60分钟、数据生命周期、一键启动、恢复、冻结与人工总验收均PASS | 商业化需换Avatar许可 |
| UX4 | PASS | 授权照片→正面化→10秒无缝Idle→双预览→人工确认→实时Avatar；196.187秒真实生产编排；四服务恢复 | 口型感知由B2/V1FINAL关闭，Idle视频不替代口型验收 |
| UX5 / UX6 | MACHINE PASS / SUPERSEDED BY UX14 VISUAL | 主舞台Idle、四视口、停止恢复和实时PCM抖动修复有效；Crop V2视觉表面已由同场景scenev1替代 | 用户完成至少三轮真实对话并签署音画同步、嘴部与Idle自然度；直连偏移只作诊断 |
| UX8 | PASS | 保守普通话词形归一、全文/segment一致、中文空格清理、900ms句中停顿；真实ASR 3/3、四进程E2E 3/3及物理麦克风人工总验收PASS | 无 |
| UX9 | PASS | 播放态噪声门、参考音色ASR强校验、三轮短期上下文与确定性短句；真实语音闭环6/6，输出CER最高10%，普通轮首响4.985～5.999秒；人工总验收PASS | 无；进一步音色自然度优化可列入V2候选 |
| UX10 | AUTOMATION PASS / IDLE SUPERSEDED | 四视口、4个本地背景和记忆链继续有效；旧眼部局部合成候选已由UX11淘汰 | 不再激活旧候选 |
| UX11 | SUPERSEDED / FALLBACK ONLY | 完整帧Idle和预览机制仍可复用；整人物Alpha预合成被用户判定边缘、发丝、光影和场景交互不可接受 | 不再作为目标路线或待激活候选 |
| UX12 | SUPERSEDED BY UX13 / RESEARCH BASE | 无人物场景→三种完整场景全身关键帧→Wan首尾约束→10秒闭环；3段均160帧/16fps、黑帧0、首尾MAE 1.8635～1.9588；主链无抠图 | 其他姿势仍是未激活候选；不得冒充UX13运行态或说话态 |
| UX13 | PASS / ACTIVE | 用户人工批准严格正脸Idle序列；intro→idle→outro、媒体SHA与Chrome切换通过 | 说话态由UX14及V1FINAL人工总验收关闭 |
| UX14 | MACHINE PASS / ACTIVE | 批准Idle完整帧构建`scenev1`说话Avatar；active/job/socket同ID；768×432单场景输出；运动比1.280，偏移+40ms，黑帧/冻结/丢帧0；live时Idle透明 | 浏览器确认始终只有一人且嘴部实际变化；清晰度/同步/自然度记入V2-X8基线 |
| UX15 | PASS | 循环Idle常驻；Intro/Outro就绪后叠加；Canvas最后帧延迟清理；全量回归与人工连续操作通过 | 无；高清与嘴部自然度转V2-X8 |
| ARCH1 | PASS | Application反向导入=0；AST门禁；后端/前端回归通过 | 无 |
| RES1 | PASS | 60分钟20完整+10打断；Windows/WSL余量与趋势门PASS | 冷启动ready前瞬时余量低，必须保留启动准入等待 |
| ACC1 | PASS | Playwright 24/24；项目所有者确认物理麦克风、听感、打断、设置与连续性人工总验收通过 | 无 |
| INST1 | PASS（AC07最低保证） | 隔离venv、7.5GB wheelhouse、替代数据根、便携工件、start×2/status/recover/stop×2共12/12步骤PASS，端口/PID归零 | AC06独立机仅为增强项 |
| V1FINAL | PASS | 自动化全绿；实时嘴部响应4/4；UX15连续性、项目所有者人工总验收、发布冻结、AC07与总门聚合PASS | 无V1阻断项；画质/口型自然度转V2-X8 |

## 3. 已完成依赖链

```text
B2.5 非TRT Cosy普通链、严格缓存与授权盲听PASS
  → B2 H.264/WebCodecs Avatar恢复PASS（OX-09）
    → B3 打断与长稳态（OX-06）PASS
      → B4 记忆与隐私 PASS
        → B5.1/B5.2 PASS
          → B5.3 本机边界替代门 PASS
            → B5.4 发布组合 → B5.5 生命周期 → B5.6 冻结 → V1FINAL人工PASS → 最终聚合
```

B5.5历史正式候选曾通过，2026-10-04独立复验又因Windows最低1,840.566MiB失败。RES1于2026-10-05关闭该红项；V1RC1又在2026-10-06以UX7/R3/RAM双门当前候选从零重跑：20完整+10打断全PASS，RAM峰值13,775.637MiB、GPU 11.219GiB、Windows/WSL最低6,181.547/8,989.289MiB，后30分钟RAM斜率0.390333MiB/min且任务/线程/队列斜率均0。

## 4. V1结论与剩余边界

已锁定的B0～B5功能开发项均有实现；ARCH1、RES1已关闭分层和资源红项。UX14以完整场景Idle构建`scenev1`实时说话工件，UX15关闭开始/结束闪动。项目所有者人工总验收、同revision发布冻结、AC07与V1FINAL聚合均PASS。V1私人研究范围内不再有未实现开发项；高清/口型自然度、多素材、多角色/空间和插件记忆明确属于V2。

## 5. V2 规划状态

项目所有者已批准V2按`体验交互优化 → 架构扩容`执行；UX13完成X3/X4“完整场景直接生成”的单活动人物首个正式运行态接入，多实体V2仍未开始：

| 阶段 | 状态 | 入口 | 计划结果 |
|---|---|---|---|
| V2-X 体验交互优化 | PLANNED / FIRST | V1FINAL及低风险体验修补关闭或书面延期；P0/P1=0 | 多源素材、三档构图、背景/外观、低幅Idle、图像描述确认、记忆工作台、说话态高清化与口型自然度升级 |
| V2-A 架构扩容 | LOCKED BY G-V2X | V2X-AC01～08全PASS | 多形象/多空间ID与路径隔离、导入导出、图谱聚类、MCP/RAG/CLI连接器 |

权威开发及验收计划为[`V2-development-plan.md`](V2-development-plan.md)，架构决策为[`ADR-013`](architecture/adr/ADR-013-v2-experience-first-expansion.md)。Docker/Compose仍是独立部署轨，不是V2-X的入口条件。
