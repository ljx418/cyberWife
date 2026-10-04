# ADR-008：V1默认TTS切换为非TensorRT CosyVoice并采用7秒首响门

## Status

Accepted（2026-09-25）；授权声音主观盲听仍是O6的人类验收项。

## Context

用户批准在技术成本过高时把普通对话首响放宽至P95≤7.0秒。相同机器、相同30条普通语料和浏览器首个非静音口径下：Qwen P50/P95为6.327/8.393秒；非TensorRT CosyVoice在加入完成轮次内存回收后为5.567/6.392秒。CosyVoice既有正确逐字稿复测CER=0.71%，本轮30/30非空；组合驻留RAM、VRAM和双侧余量达门。TensorRT则已证明尾延迟回退。

## Decision

- V1默认TTS切换为 `cosyvoice2-0.5b` 的FP16流式非TensorRT profile。
- 保留Qwen adapter和`-TtsProfile qwen`显式回退；不删除模型或用户设置。
- TensorRT profile不作为默认；vLLM/TensorRT-LLM不进入V1。
- 首响硬门为普通缓存未命中30条P95≤7.0秒，P50记录但不设硬门。
- 每轮完成后只回收CosyVoice临时CPU对象/allocator arena，不卸载模型、不清理CUDA模型缓存。

## Consequences

- 普通链P95相对本轮Qwen改善约23.8%，满足V1门槛；部署仍是一键原生进程。
- Gateway必须使用CosyVoice隔离venv，新增约1.62GB ASR ext4副本；仍在磁盘预算内。
- Qwen不再是默认，但作为可逆回退保留。
- 机器证据不能代替授权人的主观音色判断；O6在盲听≥4/5前不得宣告V1最终通过。
