# V2-X0.2 验收标准

| ID | 操作 | 硬门 |
|---|---|---|
| X02-AC01 | active时hidden→visible | 恢复事件合并；旧资源停止一次；明确回Idle |
| X02-AC02 | offline→online与pageshow连续触发 | 同一窗口只运行一个恢复任务，不创建重复会话 |
| X02-AC03 | 恢复中再次触发/旧Promise迟到 | 旧generation不得更新UI或重新打开资源 |
| X02-AC04 | Gateway探测失败后再次online | 先进入error/安全Idle；后续可重新恢复，不需刷新 |
| X02-AC05 | feature flag关闭 | 不注册生命周期监听，V1行为不变 |
| X02-AC06 | 完整资源快照 | 麦克风活动track≤1，旧音频source=0，旧avatar transport关闭 |
| X02-AC07 | 全量回归 | build、Playwright、后端测试无新增失败 |

V2X-AC10中的真实系统休眠和服务进程恢复仍需目标机故障注入；自动化浏览器事件不能代替操作系统休眠证据。
