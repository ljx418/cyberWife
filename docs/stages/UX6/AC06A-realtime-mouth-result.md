# AC-06A 实时嘴部响应修复与复验

**日期**：2026-10-07
**判定**：MACHINE PASS / BROWSER HUMAN REVIEW PENDING

## 缺陷与根因

当前Gateway每20ms发送一帧16kHz单声道PCM。Avatar的Mel特征线程历史上只等待10ms便补一帧合成静音；当批处理消费快于实时到包时，真实语音与伪静音交错，导致嘴部变化被明显稀释。此前突发式测试一次性填满队列，所以没有暴露该问题。

## 实施

- 外部PCM到达后记录单调时钟。
- 活跃批窗口内将取帧等待提高到50ms，覆盖20ms到包与调度抖动。
- 连续260ms没有外部PCM后恢复10ms Idle等待，避免空闲态阻塞。
- 打断/flush同时清除活跃时钟，旧轮不能影响下一轮。
- 新增调度抖动、实时帧不被误判静音、flush回Idle三项回归测试。

## 真实复验

测试对象：当前active avatar `wav2lip256_idle_p_7ecfeecee271a502_47cbb203_cropv2`；输入为四段项目既有CosyVoice真实WAV，按20ms实时节奏送入，不保存字幕正文。

| 样本 | 时长 | 有声/静音嘴部运动比 | 最佳相关偏移（诊断） | 黑帧 | 冻结 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| 01 | 3.64s | 1.224933 | +40ms | 0 | 0 | PASS |
| 02 | 6.16s | 1.132363 | 0ms | 0 | 0 | PASS |
| 03 | 3.40s | 1.278807 | +160ms | 0 | 0 | PASS |
| 04 | 4.40s | 1.242146 | +40ms | 0 | 0 | PASS |

四段均满足`mouth_responds_during_voice=true`、运动比>1.10、无黑帧、无冻结；服务端infer/final FPS均≥25且传输丢帧为0。私人衍生视频与时间线仅位于`~/.cyberWife/acceptance/AC06A-realtime-jitter-fix*`，不进入Git。

## 证据边界

直连Avatar采集从PCM发送时刻开始复用时间轴，没有浏览器对新turn设置的295ms Avatar lead，因此相关性峰值不能签署最终用户音画偏移。机器门只证明“当前人物嘴部会随有声段实际变化”；浏览器端`mouth_motion_observed=true`、同步度≥4/5、嘴部自然度≥4/5仍为V1阻断门。
