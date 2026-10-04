# ARCH1 预开发审计

**日期**：2026-10-05

| 风险 | 严重度 | 闭环措施 | 状态 |
|---|---:|---|---|
| 只删除import但继续依赖conn/lock | Major | 增加仓储审计查询方法与端口 | CLOSED FOR ENTRY |
| 为过静态门使用Any/局部import | Major | AST门+代码审查禁止规避 | CLOSED FOR ENTRY |
| TurnPipeline测试默认实例缺日志/指标 | Major | 纯内存指标保留应用默认；无I/O logger作为默认 | CLOSED FOR ENTRY |
| AssetStore重复实例导致根路径偏移 | Major | 组合根创建单例并注入Gateway/AvatarAssetService | CLOSED FOR ENTRY |
| 接口改动破坏现有API | Critical | 先保持构造参数兼容，运行340项回归和资产集成测试 | CLOSED FOR ENTRY |

当前7处直接反向import已逐项定位；方案不触及数据迁移或外部状态。开放Critical/Major=0，允许进入实质开发。
