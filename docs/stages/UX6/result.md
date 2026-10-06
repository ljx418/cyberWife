# UX6 阶段结果：Crop V2 已激活，等待交互复验

**日期**：2026-10-07
**阶段结论**：用户已观看同音频前后对比并批准 Crop V2，候选已通过正式仓储事务提升为当前 active avatar。2026-10-07修复实时PCM被10ms超时误插静音的问题后，四段当前人物真实采集均通过嘴部响应机器门；UX6/V1 暂不判全绿，仍需用户在完整浏览器对话中确认音画同步、嘴部自然度和 Idle 体验。

## 已完成修复

1. 主舞台直接播放当前 active derivative 的 10 秒闭环 Idle，静态写真只作为加载或故障兜底。
2. 实时 Canvas 停止或降级时透明隐藏，底层 Idle 不销毁、不暂停，消除纯黑结束画面。
3. 竖版人物在桌面 16:9 和高屏中等比 `contain`，同源模糊层补齐背景；移动端保留聚焦构图。
4. Wav2Lip 数据集从 425×283 的过大框修正为检测框 + 10px 下巴 padding；当前人物中位框为 `[194, 484, 165, 373]`，模型输入保持项目 `wav2lip_v2` 要求的 256×256。
5. 动态 Avatar 地址加入 `cropv2` 生成器修订号；同一照片/视频不会误复用旧裁切工件，旧工件保留以便回退。

## 真实证据与判定

| 验收项 | 真实结果 | 判定 |
|---|---|---|
| 四视口主舞台 | 1920×1080、1366×768、420×720、1818×2406 均无横向溢出；桌面人物等比完整显示 | PASS |
| Idle 持续播放 | 四视口 1.2 秒观察窗口均推进约 1.205 秒 | PASS |
| live→Idle | 激活后 Headless Chrome 实际请求 `_cropv2` WebSocket；结束后 Canvas 为 hidden/static/opacity 0，Idle 在 0.9 秒内推进 0.906 秒 | PASS |
| 前端回归 | Playwright 7/7 | PASS |
| 构建器/资产回归 | 单元与 API/仓储测试 15/15 | PASS |
| 激活后的 Crop V2 Avatar | 授权 CosyVoice WAV；143 视频包、0 丢帧、25.582 final FPS、153.690 infer FPS、无黑帧/冻结；首个目标视频约 225ms | PASS（传输/性能） |
| 相对运动相关性 | 最佳偏移 +40ms、相关性 0.580；0ms 相关性 0.569，略低于 +200ms 的 0.575 | NOT PASS（诊断门） |
| 候选嘴部感知 | 用户观看同音频前后对比后明确“批准 Crop V2” | APPROVED FOR ACTIVATION |
| 完整交互感知 | 激活后无限多轮真实对话的口型、Idle自然度 | WAIT HUMAN RETEST |
| 实时嘴部响应修复 | 4段CosyVoice实时节奏PCM；有声/静音运动比1.132～1.279；黑帧0、冻结0；final FPS≥25、丢帧0 | MACHINE PASS |

## 证据索引

- 激活后页面切换：`audit/v1/UX6/live-idle-transition-r3/`
- 四视口：`audit/v1/UX6/layout/`
- 激活后 Crop V2 捕获：`audit/v1/UX6/cropv2-active-final/`
- 修复前后同音频对比：`audit/v1/UX6/cropv2-before-after.mp4`

上述目录含真人衍生媒体，按隐私规则不提交 Git。

## 人工复验门

Crop V2 已按用户批准提升为当前 active avatar。V1FINAL已把复验并入`Invoke-ACC1HumanGate.ps1`：机器自动证明三轮、打断、接续、active avatar与停止后Idle推进；用户对口型同步度、嘴部自然度和Idle自然度评分，三项均须至少4/5且结束后持续Idle。相对运动相关性只作诊断，不替代这次人工复验。

2026-10-07根因复盘：Gateway按20ms发送PCM，但Avatar历史上只等待10ms便补合成静音；Mel批处理消费速度快于实时到包速度时，真实帧与伪静音交错，嘴部运动被稀释。现在外部PCM活跃批窗口内最多等待50ms，260ms无外部音频后自动回到10ms Idle等待；`flush_talk`同步清除活跃标记。直连采集没有浏览器295ms播放预留，因此相关性偏移只保留诊断价值，最终同步度仍以浏览器现场为准。
