# V2-X3.1 自动化验收报告

**结论**：X3.1-AC01～AC07 PASS；未签署X3.2/X3.3的动态画面质量。

| 验收项 | 证据 | 结果 |
|---|---|---|
| AC01 真实目录 | 4个稳定UUID；SHA由真实WebP字节计算；焦点/安全区/URL完整 | PASS |
| AC02 幂等恢复 | 真实数据连续登记两次revision均为2 | PASS |
| AC03 字节变更 | 集成测试修改真实测试文件后revision+1且SHA变化 | PASS |
| AC04 缺失/CAS安全 | 缺文件返回503且旧manifest字节不变；repository CAS既有测试全绿 | PASS |
| AC05 浏览器目录 | Playwright验证4卡片、4个待准备状态、0激活控件 | PASS |
| AC06 开关回退 | Playwright验证关闭开关后原本地背景radiogroup存在 | PASS |
| AC07 全量回归 | 前端build PASS；Playwright 50/50；后端401 passed、7 skipped | PASS |

首次并行Playwright中AC11桌面键盘用例出现一次焦点时序失败，单项重跑与随后完整50项重跑均通过；判定为既有并行时序波动，不隐瞒且未修改验收门。首次后端命令缺少`PYTHONPATH=.`导致3项导入收集错误，按项目正确入口重跑后401/7全量通过。

