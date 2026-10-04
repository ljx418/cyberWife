# ARCH1 验收结果

**日期**：2026-10-05
**结论**：PASS；NFR-07应用层依赖方向缺口关闭，不代表V1发布门已全绿。

| 验收项 | 结果 | 证据 |
|---|---|---|
| ARCH1-AC01 反向导入为0 | PASS | AST门禁扫描`application/domain/ports`，禁止`infrastructure/adapters/api`；全库文本复核为0 |
| ARCH1-AC02 组合根与六组件 | PASS | `api/server.py`集中装配；运行中`/api/v1/health`六组件均`ready` |
| ARCH1-AC03 资产行为 | PASS | 写真上传→构建→激活与Idle预览批准集成测试通过 |
| ARCH1-AC04 会话媒体语义 | PASS | TurnPipeline、WS、指标、generation回归包含在后端全量341项通过中 |
| ARCH1-AC05 审计端口 | PASS | SQL下沉`SqliteRepository.list_audit_events`，Gateway不再访问`conn/lock` |
| ARCH1-AC06 全量回归 | PASS | 后端`341 passed, 4 skipped`；前端构建通过；Playwright `11 passed`；`git diff --check`通过 |

## PRD复检与审计

- FR-04/05/11的资产合同、授权、散列和版本语义未改变。
- FR-08/09/10的事件、取消、日志和指标时序未改变。
- FR-12/14的审计返回字段、过滤和200条上限未改变。
- 新增架构测试会阻止相同反向依赖重新进入仓库。
- 开放Critical/Major规格偏差：0。

## 真实运行边界

目标机既有服务在验收时返回六组件`ready`，资源快照RAM 13.24/15.52GiB、VRAM 2.51/23.99GiB；该服务进程是在本次源码变更前启动，因此只证明运行环境与模型链仍健康。新源码行为由进程内真实SQLite/文件资产集成测试覆盖，不能把旧进程健康响应冒充为新组合根重启证据。

## 后续

按全局计划进入发布门剩余工作：Windows宿主内存余量复验、AC-11/物理麦克风用户场景、干净Windows+WSL安装演练。
