# cyberWife 模型清单与核验合同

**版本**：1.3　**日期**：2026-10-04　**状态**：B0～B5.5已验证；B5.6发布冻结中  
“用户已下载完成”记录为输入声明；在完成文件定位、哈希、许可证和实际推理前，状态不得标为 ready。

## 1. V1 固定基线

| 组件 | 目标模型/实现 | 运行位置 | 预期格式 | 当前状态 | M0 核验动作 |
|---|---|---|---|---|---|
| VAD | Silero VAD（torch.hub `silero_vad(onnx=False, opset_version=16)`） | WSL Speech Worker / CPU | torch JIT（fallback ONNX） | 已核验并冻结本机实际加载工件 `silero_vad.jit`：2,272,526 bytes，SHA256 `e1122837…bd3720`；当前 hub 默认入口无独立 `silero_vad_v5` callable；fallback `webrtcvad` | 默认入口加载、JIT哈希、16kHz流式边界、静音误触发、离线重放 |
| ASR | Faster-Whisper `large-v3-turbo` | WSL / GPU FP16；OOM 时 int8_float16 | CTranslate2 dir | B0 独立真实加载/静音推理通过；组合验收待 B1/B2 | 中文转录、显存、加载时间、离线 |
| LLM | Qwen3-14B-Instruct `Q4_K_M` | Windows llama.cpp / GPU | GGUF | B0 build 11118 `/health` + completion 通过；组合验收待 B1 | llama-server 加载、8K context、流式/取消 |
| TTS（显式回退） | Qwen3-TTS-12Hz-1.7B-Base | WSL / GPU FP16 | Hugging Face directory | 受保护回退；不与Cosy双常驻 | `HealthAggregator`按§5触发；B5重跑内容正确、资源、显式profile回退 |
| TTS（V1默认） | CosyVoice2-0.5B | WSL / GPU FP16，非TensorRT | HF revision `eec1ae6...` | `verified`；正确逐字稿30条CER=0.71%；真实Chrome普通链30/30，P50/P95=5.567/6.392s；资源达门；授权盲听5/5 | ADR-008默认；TensorRT拒绝；B5组合复核 |
| Avatar | LiveTalking + Wav2Lip256（`license_id=Wav2Lip-ResearchOnly`，见 https://github.com/Rudrabha/Wav2Lip/blob/master/LICENSE，`license_review=approved`，商业化前重新评审） | WSL / GPU | code + checkpoint | runtime_verified；fallback静态图降级 | checkpoint shape、25FPS、loopback H.264 WS、读LICENSE原文 |
| Embedding | BAAI/bge-small-zh-v1.5（输出维度 **512**，固化写入 `memory_vectors.embedding vec_f32(512)`；V1 不自动切换维度） | WSL Gateway / CPU | HF/safetensors | B0 独立真实编码 + sqlite-vec 512维往返通过 | 中文向量、维度、sqlite-vec 写入、许可证、离线镜像 |

已检查的 `C:\ComfyUI-aki-v2\ComfyUI\models` 约 419GB，包含大量图像/视频模型；其 `LLM` 目录当时为空，且未在已检查位置确认上述完整权重。模型可以引用共享目录，但不得假设 ComfyUI 的同名组件格式可被目标运行时直接加载。

**离线镜像策略**：启动器预检时校验 `~/.cache/huggingface` 已存在目标仓库 `models--*--snapshots/*` 完整快照；缺失时仅警告，不自动下载；缺主模型标记 `blocked`，阻断 M1。`RuntimeLauncher.ps1 --offline-strict` 模式下禁止任何网络下载，缺失即失败。fallback 模型合同见 `implementation-contracts.md §10`。

## 2. 每个模型必须记录的字段

```yaml
component: llm
logical_id: qwen3-14b-instruct-q4_k_m
absolute_path: <本机私有路径，不提交 Git>
filename_or_revision: <精确文件名或 commit revision>
size_bytes: 0
sha256: <64 hex>
source_url: <官方/发布者直链>
license_id: <SPDX 或原文标识>
license_review: pending|approved|blocked
runtime: <版本与启动参数>
functional_probe: <命令/测试 ID>
verified_at: <ISO-8601>
status: discovered|hashed|licensed|loadable|verified|blocked
```

私有绝对路径只放本机 `model-registry.local.yaml`（Git ignore）；仓库只保留去路径的核验报告和示例 schema。

## 3. 验证顺序与通过条件

1. **发现**：精确匹配文件/目录，拒绝只凭模糊名称。
2. **完整性**：记录 size/SHA256；多分片必须全部存在。
3. **许可证**：记录来源与私人非商业约束；冲突即 blocked。
4. **独立加载**：在目标 runtime 中实际加载并完成一条确定性 smoke。
5. **功能合同**：验证流式、超时、取消、畸形输入和健康探针。
6. **组合驻留**：按实际拓扑启动，记录 VRAM/RAM/磁盘/首包延迟。
7. **离线复测**：断网重启与推理成功，不触发自动下载或遥测。

`verified` 条件：1～7 全通过且证据可复核。路径存在、UI 写着“就绪”或其他软件能加载均不构成通过。

## 4. 资源和磁盘规划

| 项目 | 规划 | 说明 |
|---|---:|---|
| LLM VRAM | 约 9GB | 以实测为准；8K context 起步 |
| ASR VRAM | 约 3GB | OOM 首先降计算类型；与 TTS 分时调度，**不同时驻留 ≥500ms 持续时间** |
| TTS VRAM | 约 4GB | 与 ASR 分时调度优先 |
| Avatar VRAM | 约 1.3GB | 实际分辨率/FPS 会改变 |
| 瞬时峰值（"说"时刻） | 14.3GB | LLM 9 + TTS 4 + Avatar 1.3 |
| 切换峰值（≤500ms） | 17.4GB | LLM 9 + ASR 3 + TTS 4 + Avatar 1.4 |
| 安全余量 | 至少 2GB | 总峰值硬限制 22/24GB |
| V1 新增磁盘 | ≤100GB | 不重复复制现有模型；包含环境、数据、缓存、日志和证据 |

建议分配上限：依赖环境 30GB（含 Python env ~8GB + node_modules ~3GB + CUDA/MSVC 运行时）、应用私有资产/数据库 25GB（含 SQLite/WAL/备份 + 照片声音 ≤20GB）、临时缓存 20GB（LLM KV ≤10GB + 帧缓存 ≤4GB + IndexedDB ≤2GB + ASR 解码 ≤2GB）、日志/验收证据 10GB（JSONL 轮转 ≤30天 ≤5GB + 截图视频 CSV ≤5GB）、升级/安全余量 15GB（V1→V2 迁移缓冲 + 模型补丁）。超过分项需在 M0 重新批准；剩余<10GB 时停止新缓存。完整时刻表与14GB项目 RAM预算见 `implementation-contracts.md §5`。

## 5. 配置与回退

- 配置只引用 `logical_id`，`ModelRegistry` 将其映射到本机路径；业务模块不得硬编码文件名。
- 私有绝对路径只放 `config/model-registry.local.yaml`（Git ignore）；仓库内仅保留 `config/model-registry.example.yaml`（去绝对路径示例）。
- 每个适配器报告 `loaded_revision/runtime/device/dtype/last_probe`。
- OOM 回退必须是显式 profile，并在 UI 标为 degraded，不能悄悄降低质量。
- TTS 运行时回退由 `HealthAggregator` 所有：启动probe失败、同一发布候选30条普通链P95>7秒、CER>5%或资源越门时，一次性切到Qwen且本进程不自动切回；用户执行单项恢复且Cosy probe通过后，下一会话恢复。禁止双常驻和阈值震荡。
- 模型更换必须重跑对应 contract、性能、离线和许可证验收，并更新本清单。
