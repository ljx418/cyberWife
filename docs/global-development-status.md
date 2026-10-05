# cyberWife V1 全局开发状态

**快照日期**：2026-10-06（V1RC1 当前候选重签后更新）

**判定口径**：按阶段出门门禁，不按代码文件数量或局部测试数量

## 1. 结论

原B0～B5六个开发阶段加B2.5共七个工程阶段门：**7/7已有实现与目标机证据**。V1RC1在UX7后重新签署当前候选：普通Chrome链30/30、P50/P95=4.102/4.708秒；打断30/30、静音P95=1.9ms；60分钟20完整+10打断全PASS，RAM峰值13,775.637MiB、Windows最低余量6,181.547MiB。V1FINAL已具备revision绑定现场取证与AC09失败关闭总门；当前仍须用户现场执行和独立干净Windows+WSL环境。商业用途因Wav2Lip ResearchOnly为NO-GO。

## 2. 分阶段状态

| 阶段 | 当前状态 | 已有真实证据 | 仍缺内容 |
|---|---|---|---|
| G-UX / DOC-B | PASS（ACC1自动部分） | 前端方向已批准；三视口15/15完整键盘任务、Playwright 15/15；Narrator/Chrome存在 | 真读屏完整任务仍需人工听感签字 |
| B0 | PASS | 幂等生命周期、六组件真实probe | 无 |
| B1 | PASS | 真实PCM→VAD→ASR→LLM 20/20 | 无 |
| B2 | PASS（性能门） | H.264/WebCodecs双FPS≥25、故障降级与原页恢复；UX5完成A/V机器量化 | 当前人物自然度仍需V1FINAL人工评分 |
| B2.5 | PASS | Cosy普通链P95≤7s、严格缓存、授权盲听、回退 | 无 |
| B3 | PASS（授权音频） | 30次真实打断、旧轮零泄漏、压力证据 | 真实物理麦克风自由对话未自动化覆盖 |
| B4 | PASS | sqlite-vec、删除事务、no-record、30天保留 | 无 |
| B5 / V1RC1 | CONDITIONAL（自动化门PASS） | 当前候选普通链30/30、打断30/30、60分钟、数据生命周期、一键启动、恢复和冻结均PASS | Narrator、结构化物理麦克风、UX6完整主观签署、干净机安装；商业化需换Avatar许可 |
| UX4 | PASS | 授权照片→正面化→10秒无缝Idle→双预览→人工确认→实时Avatar；196.187秒真实生产编排；四服务恢复 | 口型感知/A-V偏移仍归B2未闭环项，不由Idle视频替代 |
| UX5 / UX6 | REOPENED / ACTIVATED, WAIT RETEST | 已完成主舞台Idle、四视口构图、停止后Idle恢复和Crop V2紧裁切；用户批准候选并已激活；浏览器确认实际请求新ID，传输/FPS通过 | 激活后需用户完成至少三轮真实对话并签署口型、嘴部与Idle自然度；相对运动诊断仍有一项边缘未过 |
| UX8 | MACHINE PASS / WAIT USER RETEST | 保守普通话词形归一、全文/segment一致、中文空格清理、900ms句中停顿；真实ASR 3/3、四进程E2E 3/3、Playwright 16/16 | 用户用物理麦克风复验普通话字幕与自然停顿；不得由fixture代签 |
| ARCH1 | PASS | Application反向导入=0；AST门禁；后端/前端回归通过 | 无 |
| RES1 | PASS | 60分钟20完整+10打断；Windows/WSL余量与趋势门PASS | 冷启动ready前瞬时余量低，必须保留启动准入等待 |
| ACC1 | CONDITIONAL | 三视口15/15完整键盘任务；当前Playwright 16/16；显式焦点授权的Narrator+物理麦克风签字工具已就绪 | 人工读屏听感与物理麦克风现场旅程待验 |
| INST1 | CONDITIONAL | 便携安装入口、隔离venv与7.5GB wheelhouse通过；AC06R消除开发机模型路径/私有音色/缺省Avatar隐式依赖，本地制品准备、当前机迁移、真实启动/Avatar恢复/双停PASS；执行器含双身份拒绝和五项干净前置 | 全新Windows用户+干净WSL+GPU驱动+离线制品清单上执行正式accept |
| V1FINAL | DEVELOPED / WAIT LIVE RUN | headed Chrome取证器绑定当前Git revision；AC09最终总门逐文件复核完整发布源码、现场门和干净机门，缺报告只返回PENDING且不能冒签 | 需用户在窗口可被占用时执行一次现场门；干净机仍独立 |

## 3. 已完成依赖链

```text
B2.5 非TRT Cosy普通链、严格缓存与授权盲听PASS
  → B2 H.264/WebCodecs Avatar恢复PASS（OX-09）
    → B3 打断与长稳态（OX-06）PASS
      → B4 记忆与隐私 PASS
        → B5.1/B5.2 PASS
          → B5.3 本机边界替代门 PASS
            → B5.4 发布组合 → B5.5 生命周期 → B5.6 冻结 → 独立审计 CONDITIONAL
```

B5.5历史正式候选曾通过，2026-10-04独立复验又因Windows最低1,840.566MiB失败。RES1于2026-10-05关闭该红项；V1RC1又在2026-10-06以UX7/R3/RAM双门当前候选从零重跑：20完整+10打断全PASS，RAM峰值13,775.637MiB、GPU 11.219GiB、Windows/WSL最低6,181.547/8,989.289MiB，后30分钟RAM斜率0.390333MiB/min且任务/线程/队列斜率均0。

## 4. V1结论与剩余边界

已锁定的B0～B5功能开发项均有实现；ARCH1、RES1已关闭分层和资源红项。UX6已经关闭Idle未接主舞台、停止黑屏、16:9裁切和旧工件缓存四项实现缺陷；用户批准的当前人物Crop V2现已激活。UX8已完成普通话字幕和自然停顿机器门，需用户物理麦克风复验。V1FINAL现场取证器已通过无人值守测试；INST1-AC06R已修复干净安装执行器审计中发现的三项可移植性缺陷，并在当前机完成私有数据迁移与真实运行回归。前者尚需用户现场操作，后者尚需环境管理员提供全新Windows用户和干净WSL。V1仍未全绿。
