# UX14 阶段结果：同场景单人物实时口型

**日期**：2026-10-07
**结论**：MACHINE PASS / HUMAN EXPERIENCE PENDING

## 已实现

- 当前active avatar切换为`wav2lip256_idle_p_7ecfeecee271a502_9287499f_scenev1`。
- 说话底片直接来自UX13人工批准的正脸完整场景Idle，保留768×432人物、客厅背景与固定机位。
- 前端live首帧到达后原子隐藏Idle层，Canvas全舞台cover；停止或故障再回退Idle，不同时显示两个视频人物。
- 不使用人物抠图、透明背景或第二个人物叠层。
- 每次开始对话重新读取active/job绑定；Avatar ID变化会强制关闭旧连接并重连。旧portrait、stale ID或React状态竞态均失败关闭为完整场景Idle，不再显示右侧矩形人物遮罩。

## 真实机器证据

| 项目 | 结果 |
|---|---:|
| 输入 | 项目既有CosyVoice真实WAV，16kHz单声道，20ms实时节奏 |
| 输出 | 768×432，25fps |
| infer/final FPS | 74.953 / 26.919 |
| 有声/静音嘴部运动比 | 1.279742 |
| 最佳相关偏移（诊断） | +40ms |
| 黑帧 / 冻结 / 丢帧 | 0 / 0 / 0 |
| 自动嘴部响应门 | PASS |

Headless Chromium读取真实Gateway后确认`data-avatar-presentation=complete-scene`；Idle态视频可见且Canvas隐藏，模拟合法live首帧后350ms内Idle opacity=0、Canvas opacity=1，Canvas宽度等于1440px视口。把同一live Canvas强制降为portrait时，Idle恢复opacity=1，Canvas被强制为visibility=hidden、opacity=0；每次点击开始都会再次读取active API。私人复验视频位于`~/.cyberWife/acceptance/AC06A-single-scene/`，不进入Git。

全量回归：后端375 passed/7 skipped，根测试56 passed，Avatar 16 passed，Playwright 24 passed，人工取证核心3 passed；前端生产构建与8页Draw.io XML校验通过。LLM、Speech、Avatar、Gateway四组件复验后均为healthy。

回归首轮有3个AC-11无障碍旅程失败：这些场景刻意不提供Avatar元数据接口，新同步逻辑曾错误阻断语音会话。实现已改为元数据刷新失败时继续启动语音、关闭可疑Canvas并保留完整场景Idle；同一轮完整命令重跑后24/24通过。该失败历史不作为通过证据，最终通过结果来自修复后的全量重跑。

## 未代签内容

自动化只证明单表面、真实嘴部变化和传输性能。用户仍需在至少三轮真实浏览器对话中确认：始终只有一个人物、背景/机位连续、口型同步度≥4/5、嘴部自然度≥4/5。
