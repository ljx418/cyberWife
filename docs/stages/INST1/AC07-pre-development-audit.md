# INST1-AC07 开发前审计

| 风险 | 等级 | 闭环措施 | 状态 |
|---|---:|---|---|
| 当前安装目录重复启动冒充可移植 | P0 | 强制绑定全新隔离 venv、`/tmp` 替代数据根和 no-index 安装历史证据 | CLOSED FOR ENTRY |
| AC07 冒充独立干净机 | P0 | 独立 gate/schema/assurance，报告固定写三项限制 | CLOSED FOR ENTRY |
| 手改顶层 PASS | P1 | 聚合器重新检查所有隔离字段、步骤、哈希和 revision | CLOSED FOR ENTRY |
| 旧证据与当前发布漂移 | P1 | release manifest 必须逐文件绑定隔离与离线证据 | CLOSED FOR ENTRY |
| 生命周期失败后残留进程 | P1 | finally 清理并要求五端口和 PID 记录归零 | CLOSED FOR ENTRY |
| 私人路径进入 Git 报告 | P0 | 正式报告只保存哈希、布尔、限制与步骤名 | CLOSED FOR ENTRY |

结论：无未闭环 P0/P1 阻止进入实现；真实生命周期未执行前不得签结果 PASS。
