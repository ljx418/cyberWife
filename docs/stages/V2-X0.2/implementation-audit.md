# V2-X0.2 实现后审计

**结论**：自动化实现门PASS；Critical/P0/P1=0；真实系统休眠/服务进程恢复证据待目标机验收。

- 控制器统一监听`visibilitychange/online/pageshow`，相同窗口的恢复请求共享同一Promise。
- generation在每次恢复和stop时递增；stop期间迟到Promise不会probe或更新状态。
- 恢复先调用现有`stopConversation`，它清WS、InputAudioSession、MediaSession和AvatarSession；然后才probe Gateway。
- 本阶段不调用`createSession`，因此不可能静默生成第二会话；成功明确回Idle。
- 探测失败进入error，后续online/pageshow仍可重试；不要求刷新。
- feature flag关闭时controller不创建、不注册事件；V1行为保持。

选择安全回Idle与PRD一致。当前没有Gateway resume合同，拒绝用前端保存旧session_ref冒充可续接。
