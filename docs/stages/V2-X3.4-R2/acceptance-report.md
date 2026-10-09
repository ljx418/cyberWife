# V2-X3.4-R2 自动验收报告

| 验收项 | 结果 | 证据 |
|---|---|---|
| R2-AC01 PCM状态分类 | PASS | 有声立即进入；120ms释放；持续静音切Idle；complete保留排队有声帧；旧/重复generation拒绝 |
| R2-AC02 批内状态隔离 | PASS | 混合批逐视频帧状态单测通过 |
| R2-AC03 generation收尾 | PASS | 实时、缓存单测通过；三次直接采集ack；真实产品最终轮completion=1 |
| R2-AC04 三场景真实PCM | PASS | 黑帧0、缺口0、有声连续冻结0～1、响应比1.322～1.395 |
| R2-AC05 末段硬门 | PASS | 嘴部差异比0.624～0.659；二阶抖动比0.402～0.956 |
| R2-AC06 时长与性能 | PASS | 三段音视频均8.000秒；首包461～490ms；推理54.92～57.47FPS |
| R2-AC07 全量回归 | PASS | Avatar 26；根级65；后端415（7条件跳过）；Playwright 51；前端构建PASS |
| R2-AC08 人工A/B | WAITING | 自动指标不得代签主观自然度，重点观察雨夜末段与无入场淡化切换 |

自动化结论：**PASS**。阶段结论：**WAITING HUMAN**。

真实产品链路：6/6场景通过，首响19.7～6414.6ms，最终轮`audio_completions=1`，探针退出码0。

正式红衣形象复验：自动PASS；末段嘴部差异比0.663、二阶抖动比0.542、首包512ms、推理54.68FPS。

证据目录：`/home/administrator/.cyberWife/acceptance/V2-X3.4-R2/`
