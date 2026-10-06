# V1FINAL 开发前审计

**日期**：2026-10-06
**结论**：PASS，可进入仅限验收工具与文档同步的开发。

| 风险 | 等级 | 闭环方式 | 状态 |
|---|---|---|---|
| 操作者勾选“3轮通过”但实际没有对应事件 | P1 | 浏览器 WebSocket 只读取证并按 turn 聚合 | CLOSED FOR ENTRY |
| fake media 冒充物理麦克风 | P1 | headed installed Chrome；禁止 fake media 参数；报告活动轨道和真实PCM帧增量 | CLOSED FOR ENTRY |
| 报告泄露对话或音频 | P0 | 事件载荷字段白名单；仅存类型/ID/序号/计数/时间，不存 payload 文本和二进制 | CLOSED FOR ENTRY |
| 自动化冒充读屏听感 | P1 | Narrator 五任务仍由人类逐项签字 | CLOSED FOR ENTRY |
| 自动化冒充口型自然度 | P1 | 三项1～5分仍由人类评分，低于4直接FAIL | CLOSED FOR ENTRY |
| 验收窗口抢占用户焦点 | P2 | `-AcceptFocusChange` 缺失即在启动前失败 | CLOSED FOR ENTRY |
| 验收器误杀用户Chrome/Narrator | P1 | 独立临时profile；仅关闭本次profile进程；原本运行的Narrator保留 | CLOSED FOR ENTRY |
| 当前WSL克隆冒充干净机 | P1 | INST1-AC06明确排除当前发行版及其导出克隆 | CLOSED FOR ENTRY |
| 产品范围漂移 | P1 | 不改产品API/状态机/模型，只新增离线验收器和测试 | CLOSED FOR ENTRY |

> 本文件记录V1FINAL最初入口审计。部署门后续已由所有者决议和ADR-012调整：AC07为V1最低门，AC06为增强项。

开发入口没有未闭环 Critical/P0；现场执行与所选部署报告仍须真实生成，不在无人值守开发中伪造。
