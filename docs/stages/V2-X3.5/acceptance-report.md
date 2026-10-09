# V2-X3.5 自动验收报告

| 验收项 | 结果 | 证据 |
|---|---|---|
| X3.5-AC01 两外观/六共同组合 | PASS | API schema v2返回2个confirmed appearance、3个共同scene、6个共同组合；另保留1个红衣组合 |
| X3.5-AC02 逐组合激活 | PASS | 6/6 appearance、scene、Idle、Avatar精确匹配；默认组合已恢复 |
| X3.5-AC03 原子切换与失败保持 | PASS | 单次manifest CAS；Playwright真实交互合同；旧revision返回409 |
| X3.5-AC04 真实PCM口播 | PASS | 同一8秒PCM逐组合捕获；推理帧>0、completion=1、缺口0、FPS≥25.43 |
| X3.5-AC05 跨重启恢复 | PASS | 蓝白碎花×清晨卧室在Gateway/Avatar真实重启后恢复相同MuseTalk avatar ID |
| X3.5-AC06 故障注入 | PASS | 错SHA不发布v2绑定；重复组合、缺文件、未确认appearance及错revision失败关闭 |
| X3.5-AC07 资源/隐私/回归 | PASS | 仅本机文件与loopback；单Avatar进程；418+65+26项Python与52项浏览器测试全绿 |
| X3.5-AC08 PRD/架构检视 | PASS | V2X-AC03获得真实证据；未引入Character/Space或多角色并发 |

**阶段结论：PASS / COMPLETE。** X3.1～X3.5场景与外观预设工作包关闭，允许进入X4开发前阶段门。
