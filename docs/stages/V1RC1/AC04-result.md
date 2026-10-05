# V1RC1-AC04 打断验收与 PRD 检视

**状态**：PASS（2026-10-06）

## 真实结果

| 项目 | 结果 | 判定 |
|---|---:|---|
| Windows Chrome 154 早/中/晚打断 | 各10次，30/30 | PASS |
| 用户可听静音 | P95=1.9ms | PASS（≤400ms） |
| 旧generation音频 | 0 | PASS |
| 浏览器播放域 | 每轮打断前active source>0；打断后0；AudioContext未关闭 | PASS |
| Avatar | generation 1→2；连接代次不变；重连0 | PASS |
| Generation fence | 旧轮取消后DB不再变化；旧字幕/音频0；真实第二轮完成 | PASS |
| 新轮转录 | `今天天气不错,我想和你聊聊天`，回复14字 | PASS |

证据：`audit/v1/V1RC1/AC04-interrupt30/`、`audit/v1/V1RC1/AC04-generation-fence/`。

## 控制面观察

中/晚段 `barge_in.detected` 到 `turn.cancelled` 事件约1.3–1.93秒；这是上游生成器排空后的控制确认，不是可听静音时间。各取消组件均未产生 `component_errors`，浏览器在约2ms内停止旧音频，旧generation无泄漏。该观察进入60分钟资源/队列审计，但不冒充小于1秒。

## PRD 检视

- FR-08：用户在实际播放期间可随时打断，30/30回收播放源。
- FR-09：旧generation字幕、音频、帧和DB写入均被隔离。
- FR-10：打断后真实第二问题完成ASR、LLM、TTS，无跨轮污染。
- NFR-02：浏览器用户可听静音P95 1.9ms，满足≤400ms。
- 未签署项：60分钟趋势与发布生命周期仍开放，不以30次短测代替。

开放 Critical=0，Major=0；允许进入 RC1-AC05。
