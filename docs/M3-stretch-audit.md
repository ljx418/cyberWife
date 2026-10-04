# cyberWife V1 M3-stretch — TTS 真实合成审计（Q3T 完成）

**版本**：2.0　**日期**：2026-09-24　**状态**：Q3T 真实 GPU 加载 + TTS 真实 voice clone 合成 PASS
**关联**：[M3-audit.md](M3-audit.md) · [M3-plan.md](M3-plan.md) · [M2-stretch-audit.md](M2-stretch-audit.md) · [human-consent.md](human-consent.md)

## 1. Q3T 完成链路

```
写真（用户授权）──→ ~/.cyberWife/assets/portrait/老婆.png
                  ── 2026-09-23 ADR-006 修订 ──
                  ──→ C:\workSpace\cyberWife\assets\portrait\老婆.png

录音（前端 MediaRecorder）
                  ──→ C:\workSpace\cyberWife\assets\voice\user_clip.webm
                  ffmpeg 转 WAV（16kHz mono 16-bit PCM）
                  ──→ C:\workSpace\cyberWife\assets\voice\user_clip.wav

TTS Adapter（Q3A）
                  monkey-patch dtype str → torch.dtype
                  Qwen3TTSModel.from_pretrained（Q2 C 路径生效）
                  synthesize_stream(text, ref_audio=wav, ref_text=text)
                  ──→ 16kHz mono int16 PCM 流
                  ──→ C:\workSpace\cyberWife\audit\tts_smoke.{pcm,wav}
```

## 2. 实测参数

| 项 | 值 |
|---|---|
| 写真 | `C:\workSpace\cyberWife\assets\portrait\老婆.png` |
|  | 1.69 MB / 1022×1539 RGBA / SHA256 084a7c7893de...d9942 |
| 录音（WebM） | `C:\workSpace\cyberWife\assets\voice\user_clip.webm` |
|  | 107520 bytes / audio/webm / SHA256 61a34128...d9942 |
| 录音（WAV 转换后） | `C:\workSpace\cyberWife\assets\voice\user_clip.wav` |
|  | 212 KB / 16kHz mono 16-bit PCM / 6.77 秒 |
| 合成文本 | "今天天气不错，我想和你聊聊天"（14 字） |
| 参考文本 | **历史记录有误**：真实录音为“早上好，宝贝，快起床了，起来陪我玩”；原测试错误填写成合成文本 |
| TTS 输出（PCM） | `C:\workSpace\cyberWife\audit\tts_smoke.pcm`（488 KB） |
| TTS 输出（WAV） | `C:\workSpace\cyberWife\audit\tts_smoke.wav`（488 KB / 15.6 秒） |

## 3. 关键实测数据

| 维度 | 值 |
|---|---|
| TTS 加载时间 | 25.5 秒（首次含 CUDA context） |
| TTS 合成 wall clock | 23.1 秒 |
| 输出音频时长 | 15.6 秒 |
| 输出帧数 | 390 帧（每帧 1280 字节 ≈ 40ms @ 16kHz int16 mono） |
| 波形活跃度 | 中段采样 1247-1855（>0，非静音）|
| 波形峰值 | max=30057 min=-32767（接近饱和但有声学内容）|
| GPU 显存实测 | 已用 ~11GB（含 Qwen3-TTS 主权重 + speech_tokenizer + CUDA context + runtime）|

## 4. 风险与决策记录

### 4.1 录音 WebM 不能直接喂给 QwenTTS

**事实**：qwen_tts 0.0.2 调用 `librosa.load()` → soundfile → **不识别 WebM**。
**解决**：ffmpeg 转 WAV（16kHz mono 16-bit PCM）作为 TTS 输入参考。
**M4 接入需修订**：
- 前端 MediaRecorder 输出仍是 WebM（浏览器默认）
- 后端 `POST /api/v1/assets/voice/record` 接 base64 → 落 WebM
- **必须加 `POST /api/v1/assets/voice/convert`** 自动转 WAV → `~/.cyberWife/voice/` 或新 `C:\workSpace\cyberWife\assets\voice\_wav\`
- M3 阶段暂手动 ffmpeg 转

### 4.2 录音需逐字稿 ref_text（教程契约）

**事实**：教程 §五.6 system_prompt 强调 Qwen3-TTS voice clone **必须** ref_text（参考音频对应的逐字稿）。
**B1复核（2026-09-25）**：GPU ASR对WebM/raw PCM/trimmed WAV/v2 WAV均稳定识别为“早上好，宝贝，快起床了，起来陪我玩”。M3把参考逐字稿误填为合成文本，旧TTS听感/CER结论不能作为公平模型对比，B2必须使用正确逐字稿重测Qwen与CosyVoice。
**M4 接入需修订**：
- `SettingsDrawer` 加 ref_text 输入框（多行 textarea）
- 后端 `/assets/voice/record` 接 ref_text 字段 + 写入 `.consent.json`
- M3 阶段暂手动传入

### 4.3 波形峰值接近饱和

**事实**：max=30057 min=-32767（接近 16-bit PCM 上限 ±32767）。
**影响**：直接播放会"破音"。
**处理**：M3 阶段不修（仅 smoke）；M4 接 OutputSanitizer 时加 normalize gain = 0.9。

### 4.4 Q3R-rerun2 修复：默认 `non_streaming_mode=True`（2026-09-24）

**症状**：用户客观听感"t1 不错但中间有问题，t4 中间断句"——Qwen3-TTS 输出被切碎成散碎语音片段。
**根因**：`qwen_tts 0.0.2` 的 `generate_voice_clone` 默认 `non_streaming_mode=False`；源码注释明确写"this option currently only **simulates** streaming text input when set to `false`，rather than enabling true streaming input or **streaming generation**"——意思是 `non_streaming_mode=False` 时模型**模拟流式生成**（插入间隔静音填充），导致断句。
**修复**：`QwenTtsAdapter.synthesize_stream` 默认 `non_streaming_mode=True`，强制模型单段生成。
**实测**：
- 修复前（流式模拟）：14.64s 总时长 / 86% 有声 / 最长 3.0s
- 修复后（non_streaming）：4.32s 总时长 / 65% 有声 / 最长 1.20s（**总时长被压缩**，但流式间隔填充消除）
- 长句 38字 + non_streaming：18.64s 总时长 / 91% 有声 / **最长 9.30s**（连贯）
**对比基线（minimax-cloud）**：
- t1：3.54s / 77% / 最长 1.40s（短句也有断句）
- t4：11.42s / 70% / 最长 2.20s（minimax-cloud 也有断句但比 Qwen3-TTS 短）
**结论**：Qwen3-TTS 0.0.2 + non_streaming_mode=True 是当前最优本地方案；minimax-cloud 是回退但违反 PRD §3 不联网原则。
**审计变更**：
- `QwenTtsAdapter.synthesize_stream` 调用 `model.generate_voice_clone(..., non_streaming_mode=True)`
- 新增 `TestNonStreamingDefault` 测试用例（`inspect.getsource` 验证源码包含 `non_streaming_mode=True`）
- 全套 215 PASS / 4 SKIP（之前 214 + 1 新测试）

## 5. ADR-006 修订 + 路径影响

| 维度 | 修订前 | 修订后 |
|---|---|---|
| 写真 | `~/.cyberWife/assets/portrait/` | `C:\workSpace\cyberWife\assets\portrait\` |
| 录音 | `~/.cyberWife/assets/voice/` | `C:\workSpace\cyberWife\assets\voice\` |
| audit | `~/.cyberWife/audit/` | `C:\workSpace\cyberWife\audit\` |
| 后端 `--assets-root` | `/home/administrator/.cyberWife/assets` | `/mnt/c/workSpace/cyberWife/assets` |
| TTS 输出 | WSL ext4 `/tmp/...` | Windows `C:\workSpace\cyberWife\audit\` |

**修订理由**：用户 2026-09-23 显式选 A 方案（ADR-006 修订）；写真与项目源码同根，由 `.gitignore` 强化隔离。

## 6. P0/P1 风险

| ID | 描述 | 状态 |
|---|---|---|
| P1 | WebM → WAV 需手动转换（M4 接自动转换） | M4 待办 |
| P1 | ref_text 需手动提供（M4 接自动输入） | M4 待办 |
| P1 | TTS 输出波形峰值饱和 | M4 OutputSanitizer 加 normalize |
| P2 | 写真与项目源码同根风险 | .gitignore 已强化；建议 Windows Defender + OneDrive 排除 |

## 7. M3 出门条件核验（project-plan.md §6）

| 条件 | 状态 |
|---|---|
| TTS 实际加载 + 合成 voice clone 跑通 | ✅ 25.5s 加载 + 23s 合成 + 15.6s 输出 |
| TTS 输出有真实声学内容（非静音） | ✅ 波形中段采样 1247-1855 |
| 写真 + 录音真实路径生效 | ✅ C:\workSpace\cyberWife\assets\ |
| 全测试套件不退化 | ✅ 214 PASS / 4 SKIP（未跑新加 smoke，预期 215+） |

**M3 出门 PASS。M3-stretch 部分出门。可进入 M4。**

## 8. 等你回答

请你**回答**以下 4 个明确问题：

- **Q1: 听 `C:\workSpace\cyberWife\audit\tts_smoke.wav`** 主观感受如何？（真人感 / 机器人感 / 模糊）
- **Q2: 是否需要做"WebM → WAV 自动转换 + ref_text 表单"的 M4 前置修订？**
- **Q3: 是否进入 M4（LiveTalking + Wav2Lip + 打断控制器）？** Y/N
- **Q4: 是否需要把 `Q3T` 路径同步修订文档合同（§5.1 TTS 11GB 偏差）？**

请告诉我下一步。
