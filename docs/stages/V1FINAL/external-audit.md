# V1FINAL 外部视角文档与实现审查

**日期**：2026-10-06
**范围**：PRD、目标架构、开发/验收计划、追踪矩阵、Draw.io、现场验收器与测试
**最终结论**：PASS FOR LIVE EXECUTION；不得据此提前签V1 Go。

## 第一轮：需求覆盖与范围一致性

- FR-08、FR-09、FR-10、FR-16及NFR-04/06均有明确现场证据源和失败门。
- 三轮、打断、接续、人物、Idle和健康不再由人工主观勾选；Narrator与自然度没有被自动指标冒充。
- 没有引入云服务、fake media、新模型、额外GPU常驻、桌面壳或Docker。
- INST1-AC06继续要求真实新Windows用户和干净WSL，没有用当前系统克隆替代。

结论：PASS，无规格缩减或范围漂移。

## 第二轮：证据真实性、隐私与失败语义

- WebSocket二进制帧直接忽略；JSON事件只保留`type/turn_id/event_seq/generation/order`。
- 单测向事件注入私密语句和伪音频字段，序列化后的取证对象不含私密内容。
- 完整轮必须同时存在ASR final、文本final、音频chunk/complete和浏览器播放结束；打断后还必须出现后续完整轮。
- 活动麦克风轨道、PCM帧增长、active avatar连接、live Canvas和Idle时间推进均为独立硬条件。
- 没有显式焦点授权时，实测在启动窗口前失败且进程数不变；现场FAIL/ERROR返回非零退出码。

结论：PASS，未发现虚假验收或隐私泄漏路径。

## 第三轮：可执行性、架构与文档语义

- Windows Node实际运行核心单测3/3；PowerShell AST和Node语法通过。
- 全量回归为后端356 passed/5 skipped、根22 passed、Avatar13 passed、前端build及Playwright15 passed。
- PRD、架构、计划、验收、追踪矩阵、命令清单、状态文档及8页Draw.io对当前候选与开放门描述一致；本地Markdown链接全部存在。
- `audit/v1/ACC1/human-gate.json`受`.gitignore`覆盖；服务端口在回归后均未监听。
- 产品代码和数据库schema没有变化，验收器仍通过既有公开REST/WS/DOM合同取证，未制造测试专用后门。

结论：PASS，可进入现场执行。

## 独立审计建议

本轮变更是可读的本地验收工具与文档同步，已有三轮独立视角审查、失败优先单测、Windows/WSL双Node验证及全量回归；当前没有必须交给ClaudeCode CLI才能消除的技术不确定性。ClaudeCode CLI审计不是进入现场门的必要条件。

## 开放项

1. 用户准备好焦点被占用时，执行一次V1FINAL现场门并生成真实报告。
2. 在全新Windows用户+干净WSL+GPU驱动+本地模型工件环境执行INST1-AC06。
3. 两项均PASS且无P0/P1后，才更新为V1 Go并完成最终发布冻结。
