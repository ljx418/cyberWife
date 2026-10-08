# V2-X0.2 会话生命周期自愈计划

**入口**：X0.1自动化PASS；AC09人工门已登记且不被豁免  
**目标**：页面隐藏/恢复、网络恢复和本机服务恢复后，旧资源不复活；无法安全续接时明确回Idle，不要求刷新页面。

## 实现

1. 新增`SessionLifecycleController`，统一`visibilitychange/online/pageshow`入口、串行恢复和单调generation。
2. 恢复顺序固定为：标记recovering→停止旧输入/音频/avatar/WS→探测Gateway→安全回Idle。
3. 同一恢复窗口的重复事件合并；每个异步步骤检查generation；停止后活动track/source/avatar transport为0。
4. UI显示恢复状态和明确的“已恢复，可重新开始”；不静默创建第二会话。
5. feature flag关闭时不注册监听，完整保留V1行为。

本阶段选择“明确回Idle”而不是尝试恢复同一WS session，原因是当前Gateway没有可验证的session resume token；伪续接风险高于多一次用户点击。未来若增加resume合同需新ADR。

## 回滚

关闭`v2x.lifecycle_recovery`即不创建controller；现有`stopConversation`仍是唯一资源清理路径。
