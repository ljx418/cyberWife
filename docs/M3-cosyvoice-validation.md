# M3 CosyVoice2 对比验证

**日期**：2026-09-24  
**状态**：历史实验已完成，但2026-09-25发现参考逐字稿与录音不匹配；旧CosyVoice2 CER/听感结论**失效，等待B2公平重测**，重测前不切换生产默认值

## 1. 当前技术选型结论

当前方案对目标硬件是“容量可行”，对目标体验是“尚未达标”。模块化 `TtsPort`、Windows llama.cpp + WSL2 Speech Worker、loopback-only 和模型外置配置可以保留；M3 不能按现有审计文字判定完整出门。

| 维度 | 实测/代码事实 | 判断 |
|---|---|---|
| GPU | RTX 4090 24GB；CosyVoice2 单模型峰值 allocated 3.4GB | 容量满足，仍需 LLM+ASR+TTS+Avatar 真实组合驻留 |
| RAM | 宿主 31.8GB；WSL 当前可见 15GiB | 整机满足名义规格；WSL 压力必须纳入 soak |
| 磁盘 | WSL ext4 可用约 899GB；C 盘可用约 61GB | 模型放 ext4 可行；资产继续放 C 盘会压缩安全余量 |
| 对话首响（历史门槛） | 当时PRD要求P50≤2.0s；本轮 Cosy 非流式首包 10.04s | Fail；后续G-LAT7不改变本轮历史结论 |
| 内容正确率 | 旧实验使用错误参考逐字稿，Cosy CER 76.92% | 证据失效，不作模型判断 |
| 显存 | Cosy 3.4GB vs 文档估算 5GB | Pass，且比 Qwen 路线更有余量 |
| M3 证据 | `test_gpu_residency.py` 和 `test_oom_fallback.py` 主要是公式/模拟 | 不能替代真实组合验收 |
| 全链路 | Gateway WebSocket 仍是 echo 骨架；llama-server 仍记录为 stub | FR-08/NFR-01 尚未闭环 |

因此，架构方向基本合适，但当前实现只满足“能加载/能生成”，尚不满足“内容正确、首响自然、可连续对话”。

## 2. CosyVoice2 真实验证

模型：`FunAudioLLM/CosyVoice2-0.5B`，官方权重约 4.52GiB，保存在 WSL ext4。`llm.pt`、`flow.pt`、`hift.pt`、`speech_tokenizer_v2.onnx` 和 `CosyVoice-BlankEN/model.safetensors` 的 SHA256 全部与官方 Hugging Face 元数据一致。

固定输入：

- 合成文本：`今天天气不错，我想和你聊聊天`
- 参考音频：6.78s / 16kHz / mono
- 参考逐字稿：历史误填为合成文本；真实录音逐字稿是“早上好，宝贝，快起床了，起来陪我玩”
- seed：0

| 指标 | Qwen3-TTS 既有基线 | CosyVoice2 pinned / non-stream |
|---|---:|---:|
| 输出时长 | 4.32s | 11.20s |
| 模型加载 | 既有审计 25.5s | 7.32s |
| 首个输出 | 既有文件未留首包指标 | 10.04s |
| 合成 wall time | 既有审计 23.1s（另一轮样本） | 10.07s |
| RTF | 既有审计约 1.48 | 0.90 |
| GPU peak allocated | 既有审计口径不一致 | 3.40GiB |
| Faster-Whisper 回听 | `今天天气不错我想和你聊聊天` | `忙玩快接不错取想凯妈得黑全` |
| CER | **0%** | **76.92%** |
| 结论 | 旧样本不可作为公平基线 | 旧样本不可作为公平结论，B2重测 |

可直接盲听：

- Qwen 基线：`audit/tts_ns_ns_t1.wav`
- CosyVoice2 固定依赖样本：`audit/cosyvoice2_t1_pinned.wav`
- 机器可读结果：`audit/cosyvoice-comparison-summary.json`

## 3. 本轮实现

- 新增 `CosyVoiceTtsAdapter`：zero-shot clone、离线运行、16kHz mono int16、20ms frame、首包/RTF/GPU 指标。
- 新增真实 benchmark：相同文本、相同参考音频、固定 seed，可选 streaming/non-streaming/JIT/FP32。
- 一键复测入口：`bash tests/m3/run_cosyvoice_benchmark.sh --non-streaming --output audit/cosyvoice2_rerun.wav --report audit/cosyvoice-rerun.json`。
- 修正 ONNX Runtime 1.30（CUDA 13）与本机 CUDA 12.8 不兼容的问题，验证 1.20.2 CUDA provider 可加载。
- 对本机 CosyVoice 源码中失效的 NumPy/Tensor shim 做 adapter 内兼容，不覆盖外部源码修改。
- 后端回归在新增适配器后通过；CosyVoice 合约测试覆盖离线、隐私路径、重采样和 tensor contract。

## 4. 决策与下一门槛

1. 暂不把 `[models].tts` 从 Qwen 切到 CosyVoice，也不删除 Qwen adapter。
2. CosyVoice2 暂保持 `blocked_runtime`，含义是“未通过有效对比”，不是模型权重损坏或已证明音质差。
3. 下一轮只在独立 Python 3.10 + 官方 Torch 2.3.1/CUDA 12.1 环境重测，避免与 `qwen-tts` 的 `transformers==4.57.3` 依赖冲突。
4. 同一固定语料必须先达到 CER≤5%；随后按当前PRD测浏览器全链P95≤7.0s（P50报告）、20轮成功率和组合驻留。
5. 性能测试前需确保 Windows 端无游戏/ComfyUI 等竞争负载；本轮曾观测 `FL_2024.exe` 占 GPU 94–96%，相关 streaming 时延只保留作诊断，不作模型结论。
