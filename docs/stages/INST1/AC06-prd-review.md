# INST1-AC06 PRD规格检视

> 历史检视：后续发现可移植性缺口，当前权威结论见`AC06R-prd-review.md`。

| 规格 | 实现映射 | 判定 |
|---|---|---|
| FR-17 一键生命周期 | prepare/verify/start×2/status/recover/stop×2固定编排 | ALIGNED |
| NFR-03 稳定恢复 | start/status/recover后五端点重新验证ready | ALIGNED |
| NFR-04 本机边界 | 依赖只读离线wheelhouse；模型/源码均为本地工件 | ALIGNED |
| NFR-06 可审计 | 身份、workspace、wheelhouse、Cosy revision及逐步结果可归因 | ALIGNED |
| NFR-10 模型清单 | 复用安装器17项前检和仓库模型清单，不在runner另造模型集合 | ALIGNED |
| INST1-AC06新环境 | 双身份拒绝+四项空状态，只接受真实新环境报告 | ALIGNED；正式执行OPEN |

本轮未降低安装、模型、GPU、资源或生命周期门槛；没有把当前机的隔离venv、WSL克隆或静态测试冒充独立部署。
