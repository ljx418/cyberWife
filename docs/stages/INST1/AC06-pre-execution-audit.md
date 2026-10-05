# INST1-AC06 开发前审计

> 历史审计：后续深层检查发现制品可移植性缺口，当前权威入口审计见`AC06R-pre-execution-audit.md`。

**日期**：2026-10-06
**结论**：PASS，可开发验收执行器；不可在当前机执行正式accept。

| 风险 | 等级 | 闭环 | 状态 |
|---|---|---|---|
| 当前开发机冒充干净机 | P1 | Windows SID与WSL machine-id分别与拒绝哈希比较 | CLOSED FOR ENTRY |
| 克隆当前WSL冒充新发行版 | P1 | machine-id相同即失败，即使Windows用户不同 | CLOSED FOR ENTRY |
| 身份原文泄漏 | P1 | 报告只写SHA256，不写SID/machine-id/用户名 | CLOSED FOR ENTRY |
| 安装器暗中联网 | P0 | 只允许wheelhouse模式；不暴露online开关 | CLOSED FOR ENTRY |
| 覆盖既有数据 | P0 | 数据根/config预存在即失败 | CLOSED FOR ENTRY |
| 失败遗留进程 | P1 | finally调用现有受管stop×2；启动器所有权门保持不变 | CLOSED FOR ENTRY |
| 工具测试冒充真实复现 | P1 | 文档与结果明确：当前机只跑fingerprint/负例，正式PASS必须来自新环境 | CLOSED FOR ENTRY |

没有未闭环Critical/P0。创建新用户、WSL和驱动仍由人类在外部环境准备，本轮不执行这些高风险系统变更。
