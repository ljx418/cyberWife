# cyberWife V1 M2 子阶段：首次设置、资产、人设

**版本**：1.0　**日期**：2026-09-23　**状态**：Approved for development
**目标体验**：用户不看教程也能在 5 步内完成设置，安全预览自己的照片和声音，重启后结果仍在。
**核心文档依据**：`project-plan.md §5` + `target-architecture.md §5` + `implementation-contracts.md §2/§10/§11/§26` + `acceptance-plan.md` 中与 M2 出门条件相关的 AC-01/AC-02/AC-11 局部项。

## 1. M2 范围（按 project-plan §5）

| ID | 任务 | 实施顺序 |
|---|---|---|
| M2-01 | 五步草稿 SQLite 持久化 + 进度恢复 + 授权版本记录与撤销 | **D（待真人素材）** |
| M2-02 | 图像 magic bytes/尺寸/解码校验 + 裁切预览 + 版本存储 + 原子激活 + 回退 | **D（待真人素材）** |
| M2-03 | 音频格式/时长/声道/采样率/静音检查 + 逐字稿校验 + 试听 | **D（待真人素材）** |
| M2-04 | Profile 字段 + 示例对话 + 版本冲突 + 显式保存 + 脏数据退出提示 | ✅ 现在做 |
| M2-05 | WSL 私有资产目录权限 + 相对路径 + 防路径穿越 + 临时文件清理 | ✅ 现在做 |
| M2-06 | 响应式 + 键盘 + 焦点圈闭 + ARIA + reduced-motion 自动测试 | ✅ 现在做 |

## 2. 你批准的延后范围

按你 2026-09-23 的"选 C · 进 M2 但你提供真人素材后再做 AC-02"决定：

- **M2-01 / M2-02 / M2-03 暂不实际接入真素材**；仅完成 schema 与接口层（已在 M1 完成），实际资产处理逻辑在 M2-stretch 阶段（待你提供至少 1 张照片 + 1 段音频 + 1 份逐字稿）。
- **M2-04 / M2-05 / M2-06 现在做**；这 3 项不依赖真人素材，可端到端验证。
- **AC-02 / AC-01 验收** 推迟到 M2-stretch 启动；当前 M2 用合成文件触发 happy path。

## 3. 详细任务清单

| ID | 任务 | 验收 | 文件 |
|---|---|---|---|
| M2-04a | 实现 `SettingsService` 入口（前端） | OnboardingFlow 4 步表单填字段、PUT draft 保存 | `prototype/src/features/onboarding/OnboardingFlow.tsx` |
| M2-04b | Profile 脏检查（前端） | 关闭抽屉时若有 dirty 弹"放弃/继续编辑" | `prototype/src/features/settings/SettingsDrawer.tsx` |
| M2-04c | Profile 乐观并发后端测试 | e2e PUT /profile 携带 expected_version；冲突返回 409 + asset.version_conflict 错误信封 | `backend/tests/integration/test_e2e_smoke.py`（已有） |
| M2-05a | `AssetStore` 强化：路径穿越 + magic bytes + 50MB 上限 + SHA256 | 单测覆盖 5 类异常：路径 ../ 逃逸 / magic 不匹配 / 超限 / 非字符串 | `backend/cyberwife/infrastructure/asset_store.py` + `tests/unit/test_asset_store.py` |
| M2-05b | 临时文件清理：context manager 写入 tmpdir 验证 + 自动清理 | 单测验证写入成功 + 异常路径清理 | `backend/tests/unit/test_asset_store.py` |
| M2-06a | axe-core 集成到 Playwright | e2e 跑通 axe.run 返回 0 critical | `prototype/tests/a11y/axe.spec.ts`（说明，骨架） |
| M2-06b | reduced-motion CSS 媒体查询自动验证 | Playwright emulateMedia | `prototype/tests/a11y/reduced-motion.spec.ts`（说明，骨架） |
| M2-06c | 焦点圈闭测试 | Playwright Tab/Shift+Tab 序列断言 | `prototype/tests/a11y/focus-trap.spec.ts`（说明，骨架） |

## 4. M2 验收标准（AC-M2-N）

| ID | 量化门槛 | 测试方法 |
|---|---|---|
| AC-M2-04 | Profile 脏检查触发：未保存时关闭抽屉弹确认 | Playwright 模拟 |
| AC-M2-05a | 路径穿越阻断 100% | `pytest tests/unit/test_asset_store.py::test_path_traversal` |
| AC-M2-05b | magic bytes 校验 100% | 5 类 MIME × OK/Fail 矩阵 |
| AC-M2-05c | 超 50MB 拒绝 100% | 单测 |
| AC-M2-06a | axe-core 0 critical | `pnpm playwright test a11y/axe.spec.ts` |
| AC-M2-06b | reduced-motion 不丢失必要信息 | DOM 断言 |
| AC-M2-06c | 焦点圈闭 100% 焦点进入/退出 | Playwright Tab 序列断言 |

## 5. 关键风险（按你 2026-09-23 决策已部分消减）

1. **真人素材未到位**（P0 红线） → M2-stretch 延后；AC-01/02 推迟验收。
2. **FR-02 撤销授权硬删除策略** → 已写审计问题到 M1-audit；M2 阶段接受 soft-disable 默认、hard-delete 待你确认。
3. **跨进程原子激活**（P1） → M2-stretch 验证 LiveTalking + AssetStore.activate 跨进程原子性。

## 6. 审计闭环

按 `docs/M1-audit.md` 模板，新增 `docs/M2-audit.md` 追加 M2-N 子任务审计记录。

## 7. 启动指令

```bash
cd C:\workSpace\cyberWife
PYTHONPATH=backend python3 -m pytest backend/tests/unit/test_asset_store.py -q
PYTHONPATH=backend python3 -m pytest backend/tests/integration/test_e2e_smoke.py -q
# 然后写 M2-04/M2-06 测试
```
