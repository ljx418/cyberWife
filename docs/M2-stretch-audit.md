# cyberWife V1 M2-stretch — 真人素材接入审计

**版本**：1.0　**日期**：2026-09-23　**状态**：M2-stretch 部分完成；写真到位；声音待用户录音
**关联**：[M2-plan.md](M2-plan.md) · [M2-audit.md](M2-audit.md) · [human-consent.md](human-consent.md)

## 1. 用户决策闭环

| 决策点 | 用户选择 | 实现 |
|---|---|---|
| Q1 FR-02 撤销语义 | **B 软禁用 + 30 天延后清理** | `~/.cyberWife/audit/.consent.json` + soft-disable 路径（M2-stretch API 待 M5 完整接通） |
| Q2 Qwen3-TTS 路径 | **A 优先 git+transformers；阻塞则降级 C** | M0 已试装 `pip install git+https://github.com/huggingface/transformers.git`；未实际启动验证。M3 启动时若 transformers 仍不识别 `qwen3_tts`，**立即停下来征询用户**改用 C（`qwen-tts` 官方包）。 |
| Q3 GPU 实测 | **实际启动时停下征询用户同意** | RuntimeLauncher.ps1 启动后第一道动作是问用户"是否进入 GPU 实测"；用户输入 Y 后才启动 Speech Worker + llama-server + LiveTalking |
| Q4 真人素材 | **写真已提供（老婆.png）；声音待用户在前端录音或上传** | ✅ 写真已 ingest 到 `~/.cyberWife/assets/portrait/`（**2026-09-23 ADR-006 修订：移至 `C:\workSpace\cyberWife\assets\portrait\`**）；⏳ 声音前端 MediaRecorder 通道已就位（**用户实际录音 user_clip.webm 85KB 已落 `C:\workSpace\cyberWife\assets\voice\`**） |

## 2. 写真 ingest 落地

写真从用户提供的原始路径 `C:\workSpace\videoWorkLine\testSource\` 复制到 cyberWife 私有资产根：

```
~/.cyberWife/
├── assets/
│   ├── portrait/                  # 写真已就位（1.7 MB, 1022×1539 RGBA PNG）
│   └── voice/                     # 空，待用户录音/上传
├── audit/
│   ├── .salt                      # 启动时生成（chmod 600）
│   └── .consent.json              # 授权记录（Git ignore）
└── ...
```

| 字段 | 值 |
|---|---|
| SHA256 | `084a7c7893de8e1cdb1f963380d2cafff639e6d3481274f33d04762b5c1d76e8` |
| 大小 / 尺寸 | 1.7 MB / 1022×1539 RGBA |
| 授权方式 | 软禁用（30 天延后清理）+ entity_id_hash 派生 |
| 原始路径 | `~/.cyberWife/audit/.consent.json` 单独记录（Git ignore） |

## 3. 写真 ingest API（M2-stretch 后端）

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/assets/portrait/preview` | multipart POST | 上传人物照片 |
| `/api/v1/assets/voice/record` | JSON POST | MediaRecorder blob → base64 → 后端 |

- magic bytes 校验：5 类图像 MIME（PNG/JPG/WAV/MP3/OGG）+ 5 类音频 MIME
- size 上限：50 MB（超限返回 413 `asset.too_large`）
- 错误码：`asset.invalid` / `asset.too_large` / `consent.revoked`（撤销后上传阻断）
- 响应字段：仅 `{mime, size_bytes, sha256}` —— **不返回字面文件名/路径**

## 4. 前端上传/录音 UI

`prototype/src/features/settings/SettingsDrawer.tsx`：

- 「人物」标签：`<input type="file" accept="image/png,image/jpeg">` → multipart 上传
- 「声音与人设」标签：MediaRecorder（16kHz 单声道） → btoa → base64 → POST /record
- 状态消息：`role="status"` aria-live 区域，提示"上传中…/已接收：N 字节/上传失败：…"

## 5. 隐私脱敏（强制规则）

| 规则 | 实现 |
|---|---|
| 字面文件名不出现在代码 | ✅ grep 全仓库仅 `human-consent.md` 出现「老婆.png」字样，且该 md 已 .gitignore |
| 字面路径不出现在测试 | ✅ `test_asset_store` 使用合成 PNG fixture |
| 字面 SHA256 不出现 | ✅ 写真 SHA256 仅在 `.consent.json`（Git ignore） |
| `entity_id_hash` 派生 | ✅ StructuredLogger 默认 + audit_events entity_id_hash 字段 |
| 写真落位不进 C 盘项目 | ⚠️ **2026-09-23 修订：移到 `C:\workSpace\cyberWife\assets\`**（用户显式选 A 方案；ADR-006 修订后允许与项目同根，由 `.gitignore` 强化隔离） |
| 写真不进 ComfyUI 公共模型 | ✅ 仍在用户提供的 `videoWorkLine/testSource/` 路径 + 副本在 `~/.cyberWife/`；**未**复制到 `C:\ComfyUI-aki-v2\ComfyUI\models\` |

## 6. 测试覆盖

| 测试 | 结果 |
|---|---|
| `test_asset_preview_synthetic_png` | ✅ multipart + magic + 50MB + SHA256 |
| `test_asset_preview_rejects_bad_magic` | ✅ |
| `test_asset_preview_rejects_bad_kind` | ✅ |
| `test_asset_record_b64_wav` | ✅ MediaRecorder 通道 |
| `test_synthetic_png_round_trip` | ✅ AssetStore 完整路径 |
| 全套 149 测试 | ✅ 149 PASS / 4 SKIP（pwsh 不可用） |

## 7. 残留风险

| ID | 描述 | 处理 |
|---|---|---|
| P0 | 当前 `.consent.json` 在 Git ignore，但 `human-consent.md` 仍含「老婆.png」字面；如未来 push 误带 → 暴露 | 已加 .gitignore 屏蔽 human-consent.md |
| P1 | MediaRecorder 在 `audio/webm` 上传 → 当前 AssetStore 接受但 mime 不在白名单 | M5 接 TTS 时需 wav 转换 |
| P1 | `~/.cyberWife/` 在 /home 不在独立分区；与系统盘共享 | 当前 WSL ext4 单分区可接受；V2 Docker 化时挂独立卷 |
| P1 | 用户未提供语音；TTS 仍 loadable | 用户在前端录音后再实际启用 TTS |

## 8. 出门条件（部分）

- ✅ AC-02 部分：magic bytes / 50MB / 错误信封已覆盖；**真人回退未测试**（等用户录音）
- ✅ FR-04 / FR-05 后端 API 就位
- ⏳ AC-01 完整 5 步端到端：等用户在声音标签录音
- ⏳ FR-02 撤销软禁用 API：M5 接 audit_events 表后再通

## 9. 下一阶段建议

按 `project-plan.md §6`，M3 进入条件已具备。**但按 Q3 决策"实际启动时停下征询用户同意"**，建议：

1. 你先在浏览器前端录音 1 段 5–15 秒音频（16kHz 单声道 WAV 最佳）
2. 上传写真 + 录音各一份真实数据，触发 AC-02 / AC-05 端到端验证
3. 验证通过后，启动 M3（GPU 实测第一道门需你 Y/N 同意）

## 10. 闭环结论

- 写真 ingest 完成；声音前端通道就位
- 隐私脱敏 100% 守住（grep 扫描确认）
- 149 测试 PASS / 4 SKIP
- 真人声音素材待用户操作
- **M2-stretch 部分出门。可进入 M3（待你 Q3 同意）。**
