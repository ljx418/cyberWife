# V1RC1-AC04 开发与验收计划：打断重签

## 目标

在UX7整句合成与R3首包窗口修正后的同一候选上，重新签署实时插话，不复用旧候选结果。

## 顺序

1. Windows Chrome真实模型链执行30次：early/mid/late各10次。
2. 验证有正在播放的非静音源后发送 `barge_in.detected`；静音P95≤400ms。
3. 每轮验证AudioContext不关闭、旧generation音频0、Avatar不重连且generation推进。
4. 单独运行generation fence：取消轮DB冻结、旧字幕/音频/帧0、新一轮真实ASR和回答完成、队列归零。
5. 若任一失败，保留原始证据并建立修复子阶段，不进入60分钟门。

## 交付

- `audit/v1/V1RC1/AC04-interrupt30/`
- `audit/v1/V1RC1/AC04-generation-fence/`
- 本阶段结果、PRD检视和开放风险记录。
