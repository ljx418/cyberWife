# B2.5-O6 分阶段验收报告

**日期**：2026-09-25  
**当前结论**：PASS；机器门与授权人盲听均通过，允许进入 B2 Avatar 恢复阶段

## ADR-009 证据归属

- 本阶段签署：OX-01～05、07、08、10～12。
- B2 首次签署：OX-09 Avatar 故障降级与恢复。
- B3 首次签署：OX-06 打断。
- B5：重跑 OX-01～12 与 AC 全集。

## 当前证据

| 门槛 | 状态 | 证据摘要 |
|---|---|---|
| OX-01 普通首响 | PASS | Cosy真实Edge 30/30，P50/P95=5.567/6.392秒，P95≤7秒 |
| OX-02 音质 | PASS | CER=0.71%；授权人总体盲听5/5，五段评分5/5/5/4/5 |
| OX-03 严格问候 | PASS | 真实“你好”3/3命中，P50/P95=22.653/56.284ms |
| OX-04 语义负例 | PASS | 30条普通/负例错误命中=0，均进入正常链 |
| OX-05 版本失效 | PASS | 完整版本键与失效合同通过；核心ready不等待缓存 |
| OX-07 回退 | PASS | TensorRT拒绝后非TRT正常；Qwen profile真实启动保留；不伪报ready |
| OX-08 资源 | PASS | 项目RSS约13.14GiB、VRAM约9.37GiB、宿主/WSL可用均≥2GiB、无持续swap-in |
| OX-10 离线 | PASS（阶段范围） | 模型本地加载、未触发下载；服务仅loopback；B5断网总链重跑 |
| OX-11 界面回归 | PASS | 前端生产构建与Edge浏览器合同通过；无产品路由/主操作变更 |
| OX-12 基线回退 | PASS | Qwen/Cosy profile均真实重启；无数据迁移；TRT派生产物不参与默认路径 |

后端全量回归为 263 passed / 4 skipped，前端生产构建 PASS，开放 P0/P1=0。盲听入口：[`../../../audit/v1/B2.5/O6-blind/index.html`](../../../audit/v1/B2.5/O6-blind/index.html)；归档结果：`audit/v1/B2.5/O6-blind/result.json`，SHA256=`38e1411911efdac9ed0d8358ea7b7fbd76f6de45f7749a0dfeff7f4f09a339fc`。

## 出门结论

授权人于 2026-09-25 给出总体 5/5，满足≥4/5硬门。B2.5 正式 PASS；下一阶段只签署 B2 所属 OX-09，不得提前签署 B3 OX-06。
