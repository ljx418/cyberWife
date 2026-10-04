# B2.5-O1 可观测性基线验收报告

**日期**：2026-09-25  
**结论**：O1 PASS；允许进入 O2。B2 与 B2.5 整体仍未通过。

## 真实结果

目标机使用 Windows Edge 153、Windows llama.cpp、WSL2 Speech/Avatar/Gateway、默认 Qwen3-TTS，以既有 B2 CosyVoice 30条 WAV 作为互不相同的真实语音输入。每条均经过真实 VAD/ASR、LLM、TTS、WebSocket PCM 和浏览器 AudioWorklet；没有 mock 模型或服务端首包替代浏览器确认。

| 指标 | P50 | P95 | 判定 |
|---|---:|---:|---|
| ASR final→LLM首个可播片段 | 1752.572ms | 1928.572ms | 基线事实 |
| LLM可播→TTS首包 | 4175.975ms | 6050.066ms | 主要瓶颈 |
| TTS首包→浏览器首非静音 | 218.049ms | 500.711ms | 次要抖动 |
| ASR final→浏览器首非静音 | 6010.193ms | 8196.347ms | OX-01 FAIL，待O2/O3优化 |

30/30 样本完整、非空且为 `normal`；`cache-hit/config-invalid` 均为0，没有混桶。真实数据见 [`../../../audit/v1/B2.5/O1/samples.csv`](../../../audit/v1/B2.5/O1/samples.csv) 与 [`../../../audit/v1/B2.5/O1/metrics.json`](../../../audit/v1/B2.5/O1/metrics.json)。

## 验收逐项

| ID | 结果 | 证据/说明 |
|---|---|---|
| O1-AC-01 | PASS | 四时间点严格单调，单轮标识一致 |
| O1-AC-02 | PASS | 30/30完整；原始CSV、JSON与复跑脚本已保存 |
| O1-AC-03 | PASS | Edge AudioWorklet：静音0确认，首非静音仅1次 |
| O1-AC-04 | PASS | 未知、错误generation、重复确认测试均拒绝 |
| O1-AC-05 | PASS | 三桶独立，未来两桶为0 |
| O1-AC-06 | PASS | 后端249 passed/4 skipped；前端build PASS；Windows Edge回归PASS |
| O1-AC-07 | PASS | 未修改模型、提示词、分句阈值或运行时；当前结果未伪装为改善 |
| O1-AC-08 | PASS | RAM 11.632GiB、VRAM 11.364GiB、宿主可用2.208GiB、WSL可用10.253GiB、pswpin=0、队列归零 |
| O1-AC-09 | PASS | O1 JSON/CSV敏感短语及绝对路径扫描0命中 |

## 工具链说明

WSL 内置 Chromium 因系统缺 `libnspr4.so` 无法启动；同时旧 Playwright 全量命令误收集未安装 Vitest 的 a11y 文件。验收没有放宽：改由目标 Windows Edge 153 通过 CDP 执行同等交互和真实 AudioWorklet 合同。该环境债务不影响 O1 产品合同，但应在 B5 整理统一前端测试入口。

O2筛选期间发现 Windows/WSL wall-clock 会短时漂移并造成合法确认被拒；测量合同已收紧为“服务端单调耗时 + 浏览器本地渲染差值”，wall-clock 不再参与分位数。O1原始样本保留为历史基线，后续A/B统一使用修订口径，不跨口径宣称微小收益。

## 证据

- `audit/v1/B2.5/O1/samples.csv|json`
- `audit/v1/B2.5/O1/metrics.json`
- `audit/v1/B2.5/O1/browser-contract.json`
- `audit/v1/B2.5/O1/resource-snapshot.json`
- `audit/v1/B2.5/O1/test-results.md`
- 复跑：`node tests/b25/run_o1_browser_chain.mjs 30 audit/v1/B2.5/O1`
