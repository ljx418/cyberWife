# B2.5 本机实时体验优化开发计划

**版本**：1.1  
**日期**：2026-09-25  
**状态**：PASS；O1/O2/O3R/O5/O6通过，O3路线拒绝，O4取消，授权盲听5/5

## 1. 位置与目标

B2.5 是保留的优化里程碑名称，但当前作为 **B2 出门修复分支** 前置执行。顺序固定为：

```text
B0 PASS → B1 PASS → B2 功能链完成但首响 FAIL
                         └→ B2.5 优化并真实验收
                               ├→ PASS：回填 B2 PASS → B3 → B4 → B5
                               └→ FAIL：停线，不进入 B3/B4/B5
```

这样解决旧计划中“B2 不通过不得进入 B3”与“B2.5 在 B5 前”的编号歧义。编号不代表可以绕过门禁。

目标是在既有界面体验、32GB 物理内存/约16GB空闲预算和 24GB VRAM 内，使普通问题全链首响满足用户于2026-09-25批准的P95≤7.0秒门槛，并验证严格问候预热是否提供额外体感收益。P50继续记录但不设硬门；不得用缓存样本掩盖普通链路失败。

## 2. 当前事实基线

| 项目 | B2 真实结果 | 状态 |
|---|---:|---|
| 普通全链首响样本 | 5.08s | FAIL |
| CosyVoice 独立 TTS 首包 P50/P95 | 2.55s / 3.43s | 独立 TTS PASS |
| CosyVoice CER | 0.71% | PASS |
| Avatar inferfps / 浏览器 finalfps | 114.72 / 25.006 | PASS |
| VRAM | 9785MiB / 24564MiB | PASS |
| 项目 RAM | 约13.85GiB | PASS，余量很小 |
| 后端回归 | 243 passed / 4 skipped | 代码回归 PASS |

证据：[`../../../audit/v1/B2/acceptance-report.md`](../../../audit/v1/B2/acceptance-report.md)。

## 3. 固定架构边界

- 保持模块化单体 Gateway + Windows llama.cpp + WSL2 Speech/Avatar 进程；不微服务化、不引入 Docker。
- `TtsPort`、`LlmPort`、`AvatarPort` 是稳定边界；TensorRT、TensorRT-LLM 或 vLLM 只能作为 adapter/runtime profile，不得侵入领域层。
- Qwen TTS 保留为可恢复基线；CosyVoice 未通过完整门禁前不得成为不可回退的唯一后端。
- 同一时刻只允许一个 GPU TTS 后端常驻；禁止 Qwen 与 CosyVoice 双常驻挤占约16GB内存预算。
- `WarmResponseCache` 是内存派生物，进程退出即消失，不进入 SQLite、日志或备份。
- 前端只接收现有状态与可理解的阶段详情，不新增产品路由，不暴露 TensorRT、cache hit 等技术术语。

## 4. 实施批次

### O1：基线拆分与计量（零算法变更）

允许修改：`TurnPipeline`、`MediaPipeline`、浏览器播放确认、`RuntimeMetrics`。  
任务：统一 `trace_id/session_id/turn_id/generation`，拆分 ASR final→LLM首个可播句→TTS首包→浏览器首个非静音样本；命中与未命中分桶。  
出门：同一 30 条普通语料可重复得到原始样本、P50/P95 和每段耗时；计量开销不改变结果，迟到事件不计入新 turn。

### O2：低风险流水线优化

允许修改：`SentenceScheduler`、llama.cpp 启动 profile、队列上限。  
任务：缩短首个可播分句、验证单 slot/prompt cache、减少无意义串行等待；每项单独 A/B。  
出门：普通路径不回退；RAM/VRAM不越门；任何收益不稳定的开关默认关闭。

### O3：CosyVoice TensorRT 可逆加速

允许新增：`CosyVoiceTensorRtAdapter` 或 `CosyVoiceRuntimeProfile`，不得改 `TtsPort` 语义。  
任务：固定受支持 CUDA/TensorRT/CosyVoice revision，离线构建可删除引擎；真实流式首包与 30 条质量复测；失败回退原 adapter。  
出门：CER≤5%，30/30非空无 hang；全链而非独立 TTS 达首响门；资源达门。若引擎不兼容或无净收益，记录 FAIL 并停止该路线。

### O4：LLM 推理加速条件分支

经G-LAT7重审后取消V1实施。O2R已经保留llama.cpp低风险收益；vLLM或TensorRT-LLM主要改善LLM段，却会增加部署、显存和回滚成本。在P95≤7.0秒门槛下，只要O3R真实全链达门即保留llama.cpp，不再扩大复杂度。

### O5：严格问候预热

允许新增：`WarmResponseCache`、`WarmResponsePolicy`、缓存诊断指标。  
默认完整句：`你好/嗨/早上好/晚上好/你在吗/能听见吗/谢谢/再见`，最多6项实际预热，由配置从该集合中选择。  
规范化只允许去除首尾空白、句末标点和内部空白；不做前缀、模糊或语义匹配。缓存键必须包含 `persona_version/voice_version/llm_revision/tts_revision/policy_version/text`。任一变化立即失效。  
内存上限64MiB；核心 `interactive_ready` 不等待缓存构建；磁盘<10GB或资源余量不足时跳过预热。  
出门：正例100%命中；天气、记忆、继续说、附加语义和版本失效负例100%未命中；命中 P95≤0.8s，仅作为附加体验指标。

### O6：整体验收与回填

执行 B2.5 所属的 OX-01～05、07、08、10～12、全量回归和体验对照。OX-09 由紧随其后的 B2 Avatar 恢复阶段签署，OX-06 由 B3 签署，二者均在 B5 完整重跑。只有 B2.5 所属门槛通过，才可进入 B2 Avatar 恢复；B2 通过后才进入 B3。

## 5. 迁移与回滚

1. 所有新增能力均由配置开关控制，默认从已验证基线开始。
2. 每个批次先保存 30 条普通语料基线，再只改一个变量。
3. TensorRT engine、prompt cache、预热 PCM 都是可删除派生物，不修改源模型。
4. 单轮异常先关闭对应加速；进程级不兼容回退原 adapter；资源越门关闭预热并回退基线 profile。
5. 回滚后必须重跑普通30条、负例缓存集、Avatar FPS、资源和后端回归，不能只证明服务重新启动。

## 6. 停线条件

- 普通未命中 P95>7.0s（P50仅诊断）；
- CER>5%、授权盲听<4/5、30条出现空音频或 hang；
- VRAM>22GB、项目 RAM>14GB、任一侧可用内存<2GB、持续 swap-in；
- 缓存错误命中天气/记忆/附加语义，或把命中样本混入普通首响统计；
- 旧 generation 在打断后仍产生音频、字幕、帧或持久化副作用；
- 需要再次降低已批准的7秒PRD门槛、删除 Qwen 回退、引入公网或改变已批准主界面才能继续。

任一发生即回到计划/架构审查；不得以“平均体验更快”替代硬门。
