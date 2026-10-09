# V2-X3.5 验收标准

| ID | 用户场景与操作 | 硬门 |
|---|---|---|
| X3.5-AC01 | 打开设置页查看外观和场景 | 显示2个已确认外观；至少3个共同场景形成6个可用组合；未批准组合不可点击 |
| X3.5-AC02 | 逐一激活6个组合 | 每次Idle URL、speaking avatar、appearance ID与scene ID一致；错误人物、双人物、黑帧为0 |
| X3.5-AC03 | 对话空闲时切换组合 | 一次CAS同时提交外观与场景；不重置会话；旧组合在失败时保持可用 |
| X3.5-AC04 | 每个组合输入同一真实PCM | 每组实际产生音频响应口型；口播完成回到同组合Idle；不得使用另一外观的Avatar |
| X3.5-AC05 | 刷新页面并重启Gateway/Avatar | 恢复同一active appearance+scene；实际Avatar engine/id与API一致；双Avatar常驻次数0 |
| X3.5-AC06 | 注入旧revision、错SHA、缺文件、重复组合和未确认appearance | 全部失败关闭；manifest revision、活动组合和当前会话不变 |
| X3.5-AC07 | 资源、隐私与回归 | 仅loopback/本地文件；RAM/VRAM不突破既有门；后端、Avatar、前端和根级全量回归无新增失败 |
| X3.5-AC08 | PRD与架构检视 | V2X-AC03的3场景×2外观可回退切换得到真实证据；不提前宣称V2-A多形象完成 |

AC01～08均为本阶段出门硬门；外观/Idle自然度沿用X3.3、X3.4与R2已经取得的人类签署，不重复冒签。
