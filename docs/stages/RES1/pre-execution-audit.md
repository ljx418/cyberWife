# RES1 预执行审计

| 风险 | 严重度 | 闭环措施 | 状态 |
|---|---:|---|---|
| 为过门结束用户进程 | Critical | 只读归因；非项目进程由用户决定 | CLOSED FOR ENTRY |
| 使用短测冒充60分钟 | Major | AC03短测只决定是否进入AC04 | CLOSED FOR ENTRY |
| 旧服务/重复进程污染 | Major | PID、端口、命令行三重归属后才清理 | CLOSED FOR ENTRY |
| 降低2GiB门槛 | Critical | 验收文档固定原阈值 | CLOSED FOR ENTRY |
| 假probe或fallback | Major | 读取逻辑模型ID、fallback标记并执行功能探针 | CLOSED FOR ENTRY |

开放Critical/Major审计意见=0，允许开始只读基线与归因。
