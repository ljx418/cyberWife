# V2-X3.4-R1 自动验收报告

## 范围与证据

- 输入：`/home/administrator/.cyberWife/acceptance/V2-X3.3-R1/input.wav`
- SHA-256：`5cba0620d4ecd5ada91425eb64b8e27d3244927e859774b63602e5f0109b0340`
- A/B 页面：`/home/administrator/.cyberWife/acceptance/V2-X3.4-R1/review.html`
- 原始采集：`/home/administrator/.cyberWife/acceptance/V2-X3.4-R1/*-coordmedian/`

| 验收项 | 结果 | 证据摘要 |
|---|---|---|
| R1-AC01 坐标稳定单测 | PASS | source 保持、median 固定、非法模式关闭 |
| R1-AC02 三场景同音频 A/B | REVOKED | 整段指标改善，但末段静音仍被推理为说话，存在局部音画失配 |
| R1-AC03 连续性 | REVOKED | 流连续，但 generation 尾帧范围与有效音频范围不一致 |
| R1-AC04 性能 | PASS | 首包 472～545 ms；推理 50.41～52.07 FPS |
| R1-AC05 隔离与回滚 | PASS | 独立候选 ID；manifest 显式能力；正式形象不迁移 |
| R1-AC06 人工 A/B | BLOCKED | 先修复末段口型与验收漏检，不要求人类批准已知缺陷候选 |

## 回归测试

- Avatar：21 passed
- 根级工具与合同：62 passed
- 后端：412 passed，7 skipped（既有条件跳过）
- 前端构建：PASS
- Playwright 端到端：51 passed

原自动化结论已撤销。当前阶段结论：**FAIL / RETURN TO DEVELOPMENT PLAN**。详见 `tail-defect-audit.md`。
