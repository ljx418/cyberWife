# ACC1 预开发审计

| 风险 | 严重度 | 闭环措施 | 状态 |
|---|---:|---|---|
| mock旅程冒充真实后端 | Major | 隔离但运行生产Gateway/SQLite合同；模型态另由正式服务验证 | CLOSED FOR ENTRY |
| Accessibility Tree冒充NVDA | Critical | AC05单列真实人工感知门 | CLOSED FOR ENTRY |
| 授权WAV冒充物理麦克风 | Critical | AC06只接受Windows默认录音设备 | CLOSED FOR ENTRY |
| 测试删除用户记忆 | Critical | 临时SQLite与测试记录；正式库只读 | CLOSED FOR ENTRY |
| 自动Chrome抢焦点影响用户 | Major | 执行前明确通知，结束后关闭测试实例 | CLOSED FOR ENTRY |

开放Critical/Major审计意见=0；允许先实施无焦点的自动化旅程。AC05/06执行前仍需发送焦点与录音提示。
