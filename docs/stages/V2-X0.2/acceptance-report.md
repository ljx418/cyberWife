# V2-X0.2 自动化验收报告

**自动化结论**：X02-AC01～07 PASS（浏览器/代码范围）  
**V2X-AC10系统级部分**：PENDING TARGET-MACHINE FAULT INJECTION

| 证据 | 结果 |
|---|---|
| visibility/network两个恢复请求并发 | stop=1、probe=1、recoveryCount=1、最终Idle |
| controller stop使旧generation失效 | probe=0、最终stopped |
| 首次probe失败后再次恢复 | error→idle、attempts=2，不刷新页面 |
| 前端构建与全Playwright | build PASS；32/32 PASS |
| 后端能力flag/合同回归 | 35/35 PASS；仅已通过的contracts/input/lifecycle开启 |
| 资源清理白盒 | 复用V1 `stopConversation`；WS close + input/media/avatar stop均在probe前 |

自动化浏览器事件可以证明状态机、合并、代际和调用顺序，但不能伪造Windows休眠、WSL服务进程退出或真实GPU worker恢复。AC10的目标机故障注入在G-V2X前执行。
