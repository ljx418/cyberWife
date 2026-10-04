# B3 开发前审计与开发后复核模板

**当前结论**：POST-DEVELOPMENT PASS；开放 P0/P1=0；允许进入 B4 阶段门。

## 开发前风险闭环

| 风险 | 等级 | 关闭方式 | 状态 |
|---|---|---|---|
| WS receive loop 被推理阻塞，无法收到插话 | P1 | 固定持续 receiver + active turn task + 单 sender | CLOSED IN PLAN |
| 取消 task 但底层线程继续产生数据 | P1 | adapter cancel + generation fence 双重隔离 | CLOSED IN PLAN |
| 关闭 AudioContext 同时中断麦克风 | P1 | 跟踪并停止旧 playback source，不 suspend/close 输入 context | CLOSED IN PLAN |
| Avatar/字幕迟到污染新轮 | P1 | 服务端与浏览器双侧 generation 丢弃 | CLOSED IN PLAN |
| 以1000ms回收门冒充400ms听感门 | P1 | 两种指标分列、30行原始样本 | CLOSED IN PLAN |
| 资源余量过窄 | P1 | 不新增常驻模型；每分钟采集；越门停线 | CLOSED IN PLAN |

## PRD 映射

FR-07/08/09/10、NFR-01/02/03/06/07 对应 B3-AC01～07；视觉基线未变，映射结果见 `prd-review.md`。

## 开发后独立复核

- 代码实体：`CancellationToken`、`InterruptionController`、`SessionRuntime`、`TurnPipeline`、`MediaPipeline`、Gateway 单 sender，以及浏览器 `MediaSession`/`AvatarSession` 已形成端到端 generation fence。
- 真实证据：AC01～AC07 全部 PASS；100轮成功率100%；60分钟资源 soak PASS；B2/B2.5 回归 PASS。
- 回归：后端269 passed/4 skipped，Avatar worker 3 passed，前端 production build PASS。
- 失败处置：AC05 首次19轮因单帧 Avatar 超时误降级而停止，修订为连续3次才降级后正式100轮通过；原始失败证据保留。B2.5 初次复测命中长期 Chrome 的旧 Vite 模块缓存，真实首响已有采样但播放结束不闭环；验收器禁用缓存并使用唯一模块 URL后重测通过，未更改产品门槛。
- AC06 口径复核：`持续 swap-in` 固化为连续3分钟均≥256页/分钟（1MiB/分钟）；实测峰值170页/分钟且连续材料化分钟为0。原始采样、首次计算与重算证据均保留。

## 开放项与阶段门

没有致命或重大规格偏差；没有以降级、mock 或删样本替代真实通过。B3 允许关闭并进入 B4 的开发前计划和审计，但本结论不提前签署 B4/B5。
