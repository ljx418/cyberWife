# ARCH1 详细开发计划：应用层依赖方向闭环

**日期**：2026-10-05

**前置门**：UX5 PASS；目标架构与2026-10-04阶段审计明确要求关闭NFR-07缺口

## 目标

把实际依赖收敛为`api组合根 → application → domain/ports`与`infrastructure/adapters → ports/domain`。Application目录不得导入Infrastructure；数据库schema、REST/WS合同、用户数据和现有体验保持不变。

## 实施实体

1. `ports/repositories.py`：增加应用仓储结构协议与审计查询合同。
2. `ports/assets.py`：定义资产解析/入库端口。
3. `ports/observability.py`：定义结构日志与运行时指标端口。
4. `application/runtime_metrics.py`：承载纯内存、无I/O的指标实现；删除未被生产代码使用的Infrastructure旧路径并同步测试导入。
5. `application/turn_pipeline.py`：只接收端口；默认使用无I/O日志器，不再构造基础设施实现。
6. `application/avatar_asset_service.py`：注入AssetStorePort，不再自行构造AssetStore。
7. `application/api_gateway.py`：注入RepositoryPort与AssetStorePort；审计列表通过仓储方法，不直接访问SQLite连接/锁。
8. `api/server.py`：成为唯一具体组合根，实例化SqliteRepository、AssetStore、StructuredLogger、RuntimeMetrics并注入。
9. `tests/architecture/test_dependency_direction.py`：AST静态门禁，禁止application/domain/ports导入infrastructure/adapters/api。

## 非目标与回退

- 不拆微服务、不改数据库、不迁移资产、不改UI。
- 不用`Any`或延迟import掩盖反向依赖；必须由端口和组合根真实解除。
- 单提交可回退；数据格式无变化，回退无需数据库恢复。
