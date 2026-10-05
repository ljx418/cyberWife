# V1RC1-AC05-R1 验收工具修复计划

**触发证据**：正式60分钟入口在采样前退出，`TypeError: avatar_transport() missing 1 required positional argument: 'avatar_id'`；`lifecycle.json.pass=false`，全部服务随后正确清理。

## 根因与修正

`accept_turns.avatar_transport` 已升级为显式当前人物参数，`accept_soak` 的调用点未同步。修正为：

1. 从真实 `GET /api/v1/avatar/active` 获取 active avatar id；不硬编码候选人物。
2. 只接受安全、非空 id，并传给60分钟 Avatar WebSocket。
3. 在最终manifest记录avatar id、协议版本和帧数，防止默认人物冒充当前人物。
4. 加单测覆盖有效id与异常响应；短时smoke只验证工具能进入采样，不替代60分钟正式结果。

修复完成后从零运行完整固定入口，失败批次原样保留。
