# B3 PRD 规格检视

**状态**：PASS（2026-09-26）

| PRD规格 | 真实结果 | 证据 | 判定 |
|---|---|---|---|
| FR-07 全双工输出与输入持续可用 | 单 receiver/单 sender；100轮严格事件序且无固定轮上限 | `audit/v1/B3/AC05/` | PASS |
| FR-08 用户可随时插话 | 早/中/晚30/30打断成功，静音 P95=1.7ms | `audit/v1/B3/AC01/` | PASS |
| FR-09 取消旧轮全部下游 | 旧 generation 字幕、音频、Avatar、DB 增量为0 | `audit/v1/B3/AC02-03/` | PASS |
| FR-10 新问题不受旧轮污染 | 新轮真实 ASR 文本与回答一致，延迟旧 cancel 不杀新轮 | `audit/v1/B3/AC02-03/` | PASS |
| NFR-01 首响≤7s | B2.5回归三轮 P95=4347.646ms | `audit/v1/B3/regression-b25-final/` | PASS |
| NFR-02 打断 P95≤400ms | 30样本 P95=1.7ms | `audit/v1/B3/AC01/` | PASS |
| NFR-03 单机资源门 | RAM峰值13.912GB<14GB；VRAM峰值11.218GB<22GB | `audit/v1/B3/AC06/` | PASS |
| NFR-06 长稳态 | 60分钟无崩溃/OOM/材料化持续swap，队列与task斜率0 | `audit/v1/B3/AC06/` | PASS |
| NFR-07 可恢复与可观测 | 取消故障3/3、生命周期3/3、Avatar同页恢复 | `audit/v1/B3/AC04/`、`AC07/`、`regression-b2-recovery/` | PASS |

检视未发现超出或少于 PRD 的承诺，也未改变已批准的 G-UX。B3 对应规格全部有真实证据，可进入 B4；长期 Chrome 旧模块缓存仅属于验收环境污染，已通过唯一模块 URL隔离且保留失败记录。
