# V1RC1-AC05-R1 开发前审计

**结论**：允许修复验收工具；不修改产品代码和验收阈值。

| 风险 | 闭环 |
|---|---|
| 硬编码Crop V2导致换人后假通过 | 从产品active API实时读取，并写入manifest |
| 恶意/损坏id拼入WebSocket | 限制为1–80位字母、数字、下划线、连字符 |
| smoke被当60分钟证据 | smoke使用独立目录且runner自身因<10分钟固定FAIL；只确认不再TypeError |
| 首次失败被覆盖 | `lifecycle.json`已保存；正式重跑使用新证据目录后缀`-rerun` |

开放Critical=0，Major=0；可进入最小测试工具修复。
