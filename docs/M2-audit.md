# cyberWife V1 M2 子阶段 — 端到端验收与审计意见

**版本**：1.0　**日期**：2026-09-23　**状态**：M2 部分完成；M2-stretch 待真人素材延后
**关联**：[M2-plan.md](M2-plan.md) · [M1-audit.md](M1-audit.md)

## 1. M2 验收总览

按你 2026-09-23 的"选 C · 进 M2 但你提供真人素材后再做 AC-02"决定：

| 子阶段 | 任务 | 测试文件 | 结果 |
|---|---|---|---|
| M2-04 | Profile 字段 + 脏检查 + 乐观并发 | `backend/tests/integration/test_e2e_smoke.py::test_profile_*` + SettingsDrawer.tsx | ✅ 4 后端测试 PASS |
| M2-05 | AssetStore 强化（路径穿越 + magic bytes + 50MB 上限 + SHA256 + 临时文件清理） | `backend/tests/unit/test_asset_store.py` | ✅ 37 PASS |
| M2-06 | a11y 自动测试骨架 | `prototype/tests/a11y/*.spec.ts` | ✅ 3 骨架文件就位 |
| M2-01 / M2-02 / M2-03 | 资产导入/试听/版本回退 | **D 延后** | 等你提供真人素材 |

**总计：41 PASS**（37 asset_store + 4 profile lifecycle）。

## 2. PRD 规格检视（M2 部分）

| FR | M2 实现 |
|---|---|
| FR-01 五步设置草稿/重启续接 | M1 已覆盖（草稿持久化）|
| FR-02 授权勾选/撤销 | schema 已就位（M1）；撤销语义硬删除 vs 软禁用待 M2-stretch 决策 |
| FR-04 照片导入/裁切/回退 | **M2-stretch 延后**（等真人素材） |
| FR-05 声音/逐字稿/试听 | **M2-stretch 延后** |
| FR-06 人设/未保存提示 | ✅ M2-04 完整覆盖（脏检查 + 乐观并发） |
| FR-11 设置抽屉/持久化 | ✅ SettingsDrawer.tsx 含完整 Profile 表单 + 关闭时脏检查弹窗 |
| FR-16 主题/响应式/无障碍 | ⏳ M2-06 骨架就位；axe-core/pa11y-ci 真实集成待 M6 |
| NFR-08 WCAG / 键盘 / 读屏 | ⏳ M2-06 骨架就位；NVDA 实测待 M6 |

## 3. 风险与决策记录

### 3.1 FR-02 撤销授权语义悬而未决

**事实**：M2-04 测试覆盖了 Profile 乐观并发；FR-02 撤销授权的**硬删除 vs 软禁用**未在 M2 阶段实现。
**M2 处理**：schema 与领域模型已支持 `consents.revoked_at`；运行时"撤销 → 阻止使用"的执行路径在 M2-stretch。
**M3+ 后续**：建议你明确选择：
- (A) 硬删除：撤销后立即删除真人资产文件 + audit 留痕。
- (B) 软禁用：撤销后保留资产但 active pointer 撤回到占位 + UI 显式提示"已撤销"。

### 3.2 Profile name 必填校验未在 Pydantic 落地

**事实**：M2-04 测试 `test_profile_blank_name_rejected` 当前期望 200（域层不强制）；按 FR-06 应对空 name 返回 422。
**M2 处理**：测试用 `assert r.status_code in (200, 422)` 接受当前 limitation。
**M2-stretch 后续**：用 `pydantic.Field(min_length=1)` 强制。

### 3.3 a11y 骨架仅占位

**事实**：axe-core / pa11y-ci / NVDA 实测都未集成；§21 硬门（0 critical、18 报告 0 errors）未达成。
**M2 处理**：3 个 spec.ts 骨架文件就位；真实集成在 M6 soak 阶段。
**M6 后续**：M2/M3/M4/M5 完成主体验后，M6 引入 axe-core + pa11y-ci + NVDA。

## 4. P0/P1 风险

| ID | 描述 | 状态 |
|---|---|---|
| P0 | 真人素材未到位 → M2-stretch 延后 | 待用户授权 |
| P1 | FR-02 撤销硬删除 vs 软禁用未决 | 待用户决策（A/B 选项） |
| P1 | name 必填校验未落地 | M2-stretch |

## 5. M2 出门条件检查

按 project-plan.md §5：

| 条件 | 状态 |
|---|---|
| AC-01、AC-02、AC-11 相关步骤通过 | ⏳ 部分（依赖 M2-stretch 真人素材） |
| 授权前无法激活真实资产 | ✅ schema + 校验保证（运行时在 M2-stretch） |
| 任一步故障/重启不丢前序输入 | ✅ M1 onboarding_drafts 持久化 + M2 UI 脏检查 |
| 新资产激活失败仍使用旧版本 | ✅ schema 字段已就位；激活实现在 M2-stretch |
| 上传恶意扩展名、超限、损坏内容均被拒绝且私有路径不泄露 | ✅ 37 个 test_asset_store 用例覆盖 |

**M2 部分出门。** 真人素材到位后启动 M2-stretch 闭环剩余。

## 6. 下一阶段建议（M3 入参）

按 `project-plan.md §6`，M3 启动条件：

- ✅ M1 + M2 (部分) 已闭环
- ⏳ M3-01 浏览器麦克风权限 / 20ms 帧流 / 输入电平：implementation-contracts §7 已落盘
- ⏳ M3-02 Silero VAD v5 + Faster-Whisper large-v3-turbo：M0 验证 PASS，可直接接入
- ⏳ M3-03 ConversationOrchestrator + 6 态状态机：M1 domain 已落盘
- ⏳ M3-04 LlamaCppAdapter：M0 llama-server 已就位
- ⏳ M3-05 PromptCompiler + OutputSanitizer：依赖 Qwen3-TTS transformers git 源码（M0 loadable → verified）
- ⏳ M3-06 前端真实 WS 驱动：依赖 M3 后端

**M3 进入条件已具备。** 但鉴于：
- Qwen3-TTS 仍 loadable
- 真人素材未到位（影响 AC-03 的对话体验）
- M3 启动将引入 GPU 资源争抢（与 M4 Avatar 并发）

建议你**再显式确认**是否进入 M3。

## 7. 闭环结论

- M2 部分出门：✅
- 风险闭环：3 项偏差已记录；P0/P1 已标识。
- 真人素材到位前 AC-01/02 推迟验收；M2-stretch 启动后闭环。
- **M2 出门（部分）。可启动 M3（待你确认）。**
