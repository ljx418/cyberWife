# V2-X0.2 开发前审计

**结论**：PASS；Critical/P0/P1=0。

| 风险 | 等级 | 闭环 | 状态 |
|---|---|---|---|
| 旧turn/音频恢复播放 | P1 | 先执行既有stopConversation及generation清理，再探测 | CLOSED |
| 重复恢复创建多个会话 | P1 | Promise合并；本阶段只回Idle，不自动createSession | CLOSED |
| 隐藏页面误终止正常后台短切 | P2 | hidden只标记；visible/online时才恢复清理 | CLOSED |
| 探测失败卡死 | P1 | error状态保留；下一online/pageshow可重试 | CLOSED |
| 虚假宣称系统休眠通过 | P1 | 浏览器自动门与目标机休眠AC10分离 | CLOSED |

无需修改Gateway session协议，架构冲击小且回退明确。
