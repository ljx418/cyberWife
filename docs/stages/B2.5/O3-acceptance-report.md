# B2.5-O3 CosyVoice TensorRT验收报告

**日期**：2026-09-25  
**结论**：FAIL/BLOCKED；TensorRT路线拒绝，不得切换默认，不进入O4/O5。

## 1. 实施事实

- TensorRT 10.13.3.9安装在既有CosyVoice隔离venv；未替换系统CUDA/Torch。
- 使用本地`flow.decoder.estimator.fp32.onnx`构建RTX 4090 FP16 engine，构建约58秒，engine 178310764 bytes。
- manifest绑定模型revision、源码revision、ONNX/engine SHA256、TensorRT版本、GPU和精度；缺失或不匹配fail closed。
- adapter/runtime profile可在`qwen/cosy/cosy-trt`间重启切换，`TtsPort`未改变；Qwen仍是默认。

## 2. 同环境30条公平A/B

| 路线 | 首包P50 | 首包P95 | wall P50 | wall P95 | 判定 |
|---|---:|---:|---:|---:|---|
| 当前非TRT Cosy控制组 | 2751.3ms | 3604.445ms | 2956.15ms | 4656.455ms | 控制 |
| Cosy TensorRT | 2713.3ms | 3956.8ms | 2847.35ms | 4963.53ms | **拒绝** |

TensorRT P50仅改善约1.4%，P95回退约9.8%；wall P95也回退约6.6%，不满足“可重复净收益且尾延迟不回退”。TRT生成30/30非空，真实Faster-Whisper评分CER=3.8%，质量门通过但不能抵消性能失败。

## 3. 门禁结果

| ID | 结果 | 说明 |
|---|---|---|
| O3-AC-01 | PASS | 本地构建、版本与manifest齐全，产物可删除 |
| O3-AC-02 | PASS | TRT/non-TRT profile、health和端口合同通过 |
| O3-AC-03 | **FAIL** | 30条质量通过，但P95显著回退，无净收益 |
| O3-AC-04 | NOT RUN | 独立TTS已失败，禁止用全链继续筛选好看样本 |
| O3-AC-05 | PARTIAL | manifest负例合同PASS；Qwen真实回滚最终完成 |
| O3-AC-06 | NOT SIGNED | 构建日志峰值可观察，但路线已在AC03淘汰，不签稳态 |
| O3-AC-07 | NOT RUN | 不为失败候选继续扩大验证 |
| O3-AC-08 | BLOCKED | 259 passed/4 skipped、前端build PASS；仍有开放稳定性P1 |

## 4. 回滚异常

恢复Qwen后首次真实浏览器链超时。Speech Worker日志显示从Windows挂载模型读取时出现`model.bin is incomplete`异常；文件尺寸仍为1617884929 bytes，前序独立ASR刚完成30条。重启Speech Worker后真实浏览器链完成，但冷态首响12.383秒。该问题记录为`O3-RB-01`，在根因和复现率关闭前不得宣称回滚链完全稳定。

证据：`audit/v1/B2.5/O3/{tts,control,rollback-qwen,rollback-qwen-retry}`，engine manifest位于本机CosyVoice模型目录。
