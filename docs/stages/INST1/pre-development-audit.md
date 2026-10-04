# INST1 预开发审计

| 风险 | 严重度 | 闭环 | 状态 |
|---|---:|---|---|
| 覆盖正式配置/数据 | Critical | prepare只创建缺失项，存在即拒绝覆盖 | CLOSED FOR ENTRY |
| 安装器静默联网/改防火墙 | Critical | 只校验本地工件；白盒扫描禁止网络安装命令 | CLOSED FOR ENTRY |
| 当前机verify冒充干净机 | Major | AC06单列外部环境门 | CLOSED FOR ENTRY |
| 用户名硬编码复发 | Major | 生产路径静态测试 | CLOSED FOR ENTRY |

开放Critical/Major审计意见=0，允许进入实现；AC06在缺少新环境时保持阻断。
