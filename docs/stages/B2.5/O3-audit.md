# B2.5-O3 开发前审计

**日期**：2026-09-25  
**结论**：PASS，允许按固定边界实施

## 独立审计结论

- 上游CosyVoice2原生支持`load_trt`，目标只加速flow decoder；这比引入Triton Server或TensorRT-LLM更小、更可逆。
- 本地模型已包含约286MB的decoder ONNX，不需要重新导出或下载模型；TensorRT Python包当前缺失，必须固定版本后才允许构建。
- 现有adapter硬编码`load_trt=False`，改动应停留在构造参数和composition root；禁止领域层感知TensorRT。
- engine与GPU/TensorRT强耦合，必须用manifest拒绝陈旧产物，不能只凭文件存在判ready。
- 独立TTS成绩不能替代浏览器全链；O3-AC-04保持PRD原始门槛，避免虚假验收。

## 风险闭环

| 编号 | 严重度 | 风险 | 闭环 |
|---|---|---|---|
| O3-A-01 | P1 | TensorRT 10与上游API不兼容 | 先独立build/load smoke；失败拒绝，不修改上游源码掩盖 |
| O3-A-02 | P1 | engine在驱动/GPU变化后错误加载 | manifest绑定ONNX SHA、TRT、GPU、精度；不匹配fail closed |
| O3-A-03 | P1 | 双TTS常驻越过内存 | 重启Gateway切换，禁止Qwen/Cosy双常驻 |
| O3-A-04 | P1 | 独立首包好看但全链仍失败 | 强制30条真实Edge全链门 |
| O3-A-05 | P2 | 主观音色由Agent虚假签署 | 机器仅签CER/音频完整性；盲听留O6人类门 |

开放P0：0；开放P1：0。允许实质开发。

## 开发后审计

- engine构建、manifest和fail-closed合同完成；没有修改上游源码来掩盖TensorRT警告。
- 同环境30条证明TRT P50仅改善约1.4%、P95回退约9.8%，触发O3-AC-03失败，候选已拒绝。
- 未运行完整TRT浏览器30条，因为独立阶段已失败；继续运行并选择性报告会增加虚假验收风险。
- Qwen默认已恢复；后端259 passed/4 skipped、前端build PASS。
- 开放P1：`O3-RB-01`，Speech Worker在第一次回滚真实链中出现一次Windows挂载模型读取不完整，重启后恢复但根因/复现率未关闭。

开放P0：0；开放P1：1。状态BLOCKED，需用户确认后重新规划，不进入O4/O5。
