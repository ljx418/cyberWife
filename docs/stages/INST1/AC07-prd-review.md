# INST1-AC07 PRD规格检视

| PRD/决议 | 实现映射 | 判定 |
|---|---|---|
| G-PORT单机条件 | AC07默认策略，无第二台物理机依赖 | ALIGNED |
| FR-17一键生命周期 | start×2/status/recover/stop×2，端口/PID归零 | PASS；真实Windows/WSL链已执行 |
| NFR-04本机隐私 | 离线验证，不保存音频/对话/私有路径 | ALIGNED |
| NFR-06真实状态 | 中间失败留痕并修复；只接受当前revision最终报告 | PASS |
| 16GB空闲预算 | 不新增常驻服务或模型，只串行复用当前四组件 | ALIGNED |
| 未覆盖边界 | Windows身份、WSL machine-id、GPU驱动均相同 | EXPLICIT LIMITATION |

本阶段只调整部署证据等级，不修改实时对话、打断、口型、Idle、记忆、隐私和性能规格。
