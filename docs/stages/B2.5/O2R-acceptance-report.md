# B2.5-O2R 宿主内存修复验收报告

**日期**：2026-09-25  
**结论**：PASS；关闭`O2-RAM-01`，允许进入O3。

## 1. 候选结果

| 候选 | 结果 | 资源/性能结论 |
|---|---|---|
| R1 `parallel=2 + kv-unified` | REJECT | 保持4096上下文后60秒Windows Available末值1988MiB，低于2048MiB |
| R2 `--no-host` | SELECTED | 4 slot/4096上下文不变；30/30；P50/P95=5.913/7.827秒；资源达门 |

首次R1未显式统一KV时日志显示每slot仅2048，该样本作废；修正后才进入资源判定，没有以缩水上下文换取内存。

## 2. R2真实确认

- 10条筛选：10/10，P50/P95=5.701/7.275秒。
- 30条确认：30/30，每轮唯一浏览器播放确认且有非静音PCM；P50/P95=5.913/7.827秒。
- 恢复基线：P50/P95=6.459/8.011秒；R2分别改善约8.5%和2.3%，没有性能回退。
- 30轮后Windows Available六次为2849/2911/2908/2892/2832/2844MiB；全回归后的瞬时下降经OS自然回收后连续18次为3372～3513MiB。
- WSL Available约9.8GiB；项目RAM约10.6GiB；VRAM约11.7GiB；swap-in=0。

## 3. 回归

- 后端：255 passed / 4 skipped。
- 前端生产构建：PASS，21 modules。
- Windows Edge 153浏览器合同：PASS。
- 默认启动器现启用`--no-host`，可用`-LlamaNoHost:$false`一轮回滚，无数据迁移。

证据：`audit/v1/B2.5/O2/resume-selected`、`audit/v1/B2.5/O2R/R1`、`audit/v1/B2.5/O2R/R2`、`audit/v1/B2.5/O2R/browser-contract.json`。
