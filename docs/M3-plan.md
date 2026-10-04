# cyberWife V1 M3 子阶段：VAD / ASR / LLM 与状态机

**版本**：1.0　**日期**：2026-09-23　**状态**：Approved for development
**目标体验**：一次点击后自然说话，系统听懂并快速生成符合人设的短回复和字幕。
**核心文档依据**：`project-plan.md §6` + `target-architecture.md §5` + `implementation-contracts.md §6/§7/§18/§27` + `acceptance-plan.md AC-03/04/05` + 用户 2026-09-23 Q3 决策（GPU 实测前停下）。

## 1. Q3 GPU 实测门（关键门槛）

按用户 2026-09-23 决策，**任何调用 GPU 的代码路径**必须经以下门控：

| 测试 | 预期结果 |
|---|---|
| `nvidia-smi` | 列出 RTX 4090 / 24GB |
| `python -c 'import torch; print(torch.cuda.is_available())'` | True |
| `python -c 'import torch; print(torch.cuda.get_device_name(0))'` | GPU 型号 |
| `python -c 'import torch; print(torch.cuda.mem_get_info(0))'` | total > 22GB |
| llama-server :8090 启动 + curl /health | 200 |
| Faster-Whisper large-v3-turbo 加载（首次 GPU 测试） | 加载时间 < 30s；VRAM ≈ 3GB |
| Qwen3-TTS Base 加载（若 Q2 A 成功） | 加载时间 < 30s；VRAM ≈ 4GB |
| 组合驻留峰值 | ≤ 17.4GB（§5.1 切换峰值） |

**任一失败 → 立即停下 + 回到 Q3 征询用户**。

## 2. M3 子任务清单

| ID | 任务 | 验收 | 文件 |
|---|---|---|---|
| M3-01 | 前端 AudioContext + AudioWorklet + 20ms PCM Int16 LE 16kHz WS 二进制帧 | AudioWorklet 工作；WS binary 帧格式符合 §7 | `prototype/src/services/MediaSession.ts` + AudioWorklet |
| M3-02 | Silero VAD + Faster-Whisper Adapter（按 Q2 A 用 git transformers；按 Q2 C 用 qwen-tts 官方包） | VAD 1s 静音 0 误触发；ASR 1s 静音返回空 | `backend/cyberwife/adapters/{SileroVadAdapter,FasterWhisperAdapter}.py` |
| M3-03 | ConversationOrchestrator + 6 态状态机 + WS envelope + event_seq 单调 | 状态机属性测试 36 单元通过；迟到事件丢弃 | `backend/cyberwife/application/conversation_orchestrator.py` |
| M3-04 | LlamaCppAdapter 流式 + cancel + llama-server :8090 健康探测 | 1 token 流式返回；cancel 后 token 不再增长 | `backend/cyberwife/adapters/LlamaCppAdapter.py` |
| M3-05 | PromptCompiler + OutputSanitizer + Qwen3-TTS 真实加载（依赖 Q2 决定） | prompt 拼装；output 去 Markdown/emoji；TTS 至少 loadable | `backend/cyberwife/application/{prompt_compiler,output_sanitizer}.py` + `backend/cyberwife/adapters/QwenTtsAdapter.py` |
| M3-06 | 前端真实 WS 驱动 | 收 reply.text.delta / reply.audio.chunk | `prototype/src/features/conversation/ConversationScreen.tsx` + `prototype/src/services/ConversationClient.ts` |
| M3-07 | GPU 资源实测（Q3 门） | VRAM 组合驻留 ≤ 17.4GB；OOM 回退 profile | `backend/tests/m3/test_gpu_residency.py` |

## 3. M3 验收标准（AC-M3-N）

| ID | 量化门槛 |
|---|---|
| AC-M3-01 | 前端 AudioWorklet 20ms PCM 帧 + 电平事件 ≤ 50ms 间隔 |
| AC-M3-02 | ASR 1s 中文静音返回空 segments |
| AC-M3-03 | VAD 1s 中文静音返回 0 误触发 |
| AC-M3-04 | 状态机 6×6 36 单元无非法跳转 |
| AC-M3-05 | WS 迟到事件被丢弃（event_seq ≤ seen 丢弃率 100%） |
| AC-M3-06 | llama-server :8090 /health 返回 200 + completion endpoint 流式 1 token |
| AC-M3-07 | Prompt 注入 ≤ 4096 token；OutputSanitizer 移除 Markdown/emoji/动作括号 |
| AC-M3-08 | GPU 资源实测：组合驻留峰值 ≤ 17.4GB |

## 4. 关键风险（Q3 决策点）

1. **Q2 A 失败**（git transformers 不识别 qwen3_tts）→ 立即停下征询用户选 C
2. **GPU OOM**（任意组件实际驻留超 22GB）→ 触发 OOM 回退 profile（§5）；仍 OOM → 立即停下征询
3. **真人声音未到位**（用户未在前端录音）→ AC-03 端到端对话用合成语料跑 happy path；真人声音到位后重测
4. **avatar 真机联调**（LiveTalking WSL2 + 写真）→ 留 M4；M3 不接入 Avatar

## 5. 启动指令

```bash
cd C:\workSpace\cyberWife
# 1. Q3 GPU 实测门（前置）
bash tests/m3/preflight_gpu.sh

# 2. Q2 A 路径：git transformers（Q3 门通过后再跑）
pip install --break-system-packages git+https://github.com/huggingface/transformers.git

# 3. M3 子任务按 M3-01 → M3-07 顺序执行
PYTHONPATH=backend python3 -m pytest backend/tests/ -q
```

## 6. 审计闭环

按 M1/M2 audit 模板，新增 `docs/M3-audit.md`。
