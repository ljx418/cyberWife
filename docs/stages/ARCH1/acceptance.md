# ARCH1 验收标准

| ID | 场景/操作 | 证据 | 出门门槛 |
|---|---|---|---|
| ARCH1-AC01 | 扫描application/domain/ports import图 | AST架构测试 | 对infrastructure/adapters/api反向导入为0 |
| ARCH1-AC02 | 启动组合根并执行六组件probe | `/api/v1/health` | 六组件均ready，具体实现只由`api/server.py`组装 |
| ARCH1-AC03 | 上传、生成、激活、恢复人物资产 | 资产API集成测试 | 合同、散列、授权和版本行为无回退 |
| ARCH1-AC04 | 创建会话并走真实文本/媒体管线 | 后端单元/集成与既有真实链证据 | 事件、指标、日志、generation语义不变 |
| ARCH1-AC05 | 查询审计记录 | API测试 | 不直接暴露conn/lock；过滤与200条上限不变 |
| ARCH1-AC06 | 全量回归与白盒审查 | pytest、Playwright、egress扫描 | 新增P0/P1=0；隐私和本地边界不变 |

## 出门条件

全部AC通过、后端全量测试无新增skip、静态import门为0，目标架构与全局状态同步后才能签ARCH1 PASS。
