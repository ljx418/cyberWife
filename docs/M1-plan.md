# cyberWife V1 M1 子阶段：运行骨架、数据层与契约

**版本**：1.0　**日期**：2026-09-23　**状态**：Approved for development
**目标体验**：一次命令可启动、查看、恢复和关闭所有组件；页面不再把固定数组当真实状态。
**核心文档依据**：`project-plan.md §4` + `target-architecture.md §3/§6/§7` + `implementation-contracts.md §1–§30` + `acceptance-plan.md` 中与 M1 出门条件相关的 AC-12/AC-13/AC-14 局部项。

## 1. M1 范围（与 project-plan §4 对齐）

- 后端目录骨架：`backend/cyberwife/{api,application,domain,ports,adapters,infrastructure}/`
- Domain 层：纯 Python 类型与不变量（无框架依赖），覆盖 Session/Turn/Memory/Profile/Asset/Consent
- Ports：ASR/LLM/TTS/Avatar/Embedding/Repository 共 6 个抽象接口
- Application：`ApiGateway.py` + `HealthAggregator.py` + `ModelRegistry.py`（3 个最小可运行）
- Infrastructure：`SqliteRepository.py` + `VectorIndex.py` + `AssetStore.py` + `StructuredLogger.py`
- Data：`migrations/0001_init.sql`（已含全部 §2 表）+ `schemas/{rest,ws,events,errors}/`（9 REST + 8 WS + 1 domain_events + 1 error envelope = 19 个 JSON Schema 草案）
- Ops：`ops/windows/{RuntimeLauncher.ps1, StartLlamaCpp.ps1, ResolveWindowsHost.ps1}`（3 个 PowerShell 脚本）
- Frontend：`prototype/src/` 下 `app/AppShell.tsx` + `features/onboarding/OnboardingFlow.tsx` + `features/conversation/ConversationScreen.tsx` + `features/settings/SettingsDrawer.tsx` + `services/ConversationClient.ts` + `services/MediaSession.ts` + `platform/HostBridge.ts`（7 个文件，含 HostBridge；保留 `App.tsx` 既有视觉）
- 配置：`config/default.example.toml`（含 §17 全部字段）
- 测试：`tests/integration/` 含 DB 迁移、model functional probe、Win↔WSL 通信

## 2. 详细任务清单（M1-01 ~ M1-12）

| ID | 任务 | 验收 | 文件 |
|---|---|---|---|
| M1-01 | 创建后端目录 + Python 依赖锁 | `pip install -r backend/requirements-m1.txt` 全 OK | `backend/requirements-m1.txt` |
| M1-02 | 写 26 个 JSON Schema 草案 | `python -c 'import jsonschema, json, glob; ...'` 全部能校验 fixture | `schemas/{rest,ws,events,errors}/*.schema.json` |
| M1-03 | 写 domain 层（纯类型） | `python -c 'from cyberwife.domain.conversation import Session, Turn'` OK | `backend/cyberwife/domain/{conversation,profile,memory}.py` |
| M1-04 | 写 6 个 ports 接口 | mypy 无 strict 报错 | `backend/cyberwife/ports/*.py` |
| M1-05 | 写 3 个最小 application（ApiGateway/HealthAggregator/ModelRegistry） | `pytest tests/integration/test_health.py` 全 PASS | `backend/cyberwife/application/*.py` |
| M1-06 | 写 infrastructure 4 个类（SqliteRepository/VectorIndex/AssetStore/StructuredLogger） | `pytest tests/integration/test_sqlite.py` 全 PASS | `backend/cyberwife/infrastructure/*.py` |
| M1-07 | 写 `migrations/0001_init.sql` | `sqlite3 db.db < 0001_init.sql` 全部表创建 | `migrations/0001_init.sql` |
| M1-08 | 写 `RuntimeLauncher.ps1` + 2 个辅助脚本 | PowerShell 5.1：`Get-Help ./RuntimeLauncher.ps1 -Examples` 不抛错 | `ops/windows/*.ps1` |
| M1-09 | 拆前端 7 个文件 + 保留 `App.tsx` 视觉 | `npm run build` 不报 TS 错，路由切换正常 | `prototype/src/{app,features,services,platform}/*` |
| M1-10 | 写 `default.example.toml` | `toml.load` 全部段解析 OK | `config/default.example.toml` |
| M1-11 | 端到端：start → 启动 → health → SQLite 创建 → curl /health 返回真实状态 | AC-M1-01~05 PASS | `tests/integration/e2e_smoke.py` |
| M1-12 | PRD 规格检视 + 落盘审计意见 | 见 §5 | `docs/M1-audit.md` |

## 3. M1 验收标准（AC-M1-N 量化门）

| ID | 量化门槛 | 测试方法 |
|---|---|---|
| AC-M1-01 | `start` 两次不产生重复进程 | `bash tests/integration/test_launcher_idempotent.sh` |
| AC-M1-02 | `status` 不以 PID 存在冒充模型 ready | `curl :7860/health` 显示 functional_probe 状态而非 "alive only" |
| AC-M1-03 | `stop` 无残留监听端口 | `ss -tlnp \| grep -E '7860\|8090\|8091\|8010'` 空 |
| AC-M1-04 | REST/WS 契约测试全绿 | `pytest tests/contract/ -q` exit 0 |
| AC-M1-05 | SQLite schema migration 可从空库运行，失败不破坏原库 | `pytest tests/integration/test_migration.py` |
| AC-M1-06 | 浏览器显示真实健康状态，断开组件可降级/error | `tests/integration/test_health_states.py` |
| AC-M1-07 | 19 个 JSON Schema 全部能校验 fixture | `python -m tests.contract.test_schemas` exit 0 |
| AC-M1-08 | `default.example.toml` 含 §17 全部 10 段 | `pytest tests/config/test_example_toml.py` |
| AC-M1-09 | 前端 `prototype/src/` 7 文件全部就位 | `bash tests/build/test_frontend_split.sh` |
| AC-M1-10 | PRD §11 流程：FRS-01 五步设置 ready / 真实状态 / 持久化 UI 骨架就绪 | 手工截图 + `grep` 关键类 |

## 4. 关键风险与前置决策（不再回退）

1. **TTS 仍 loadable**（transformers 5.17 不识别 qwen3_tts）→ M1 不加载真实 TTS，仅写 ports 接口 + 1 个 mock adapter 返回预设音频。M3 阶段再处理。
2. **VAD v5 显式 callable 废弃** → M1 写 ports 时按 `silero_vad` 默认入口合同，不锁 v5 字符串。
3. **Llama.cpp b11118** → M1 用 `--no-display-prompt` 等 b11118 兼容参数；`StartLlamaCpp.ps1` 调用形式按 b11118 CLI 调整。
4. **合成语料不作为 AC 验收** → M1 端到端仅验证 API/契约/健康状态/迁移/幂等，不调用 LLM/ASR/TTS 真实推理（避免 GPU 资源）。M2 起逐步接入真实推理。
5. **真人素材缺失** → FR-02 授权门槛在 M2 实现 UI 占位（写入 SQLite 但不实际加载资产），真人素材待后续提供。

## 5. 审计意见闭环机制

每个 M1-N 子任务完成后，写 `docs/M1-audit.md` 追加：

```
### M1-N audit (YYYY-MM-DD HH:MM)
- 任务: ...
- 端到端验收: AC-M1-XX PASS/FAIL
- PRD §6/§7 FR/NFR 覆盖: ...
- 偏差记录: ...
- P0/P1 风险: ...
- 下一阶段建议: ...
```

任一条出现 **P0/P1 偏差** 即停手并按用户原话"打回到开发计划阶段重新思考并执行"。

## 6. 出 M1 范围（不阻塞 M2 启动的可选项）

- 配置加密与 KMS（V1 不要求）
- 真实 TTS 流式输出（M3 处理）
- Avatar WebRTC 实链路（M4 处理）
- GPU 显存实测（资源预算验证留 M6 soak）

## 7. 启动指令

```bash
cd C:\workSpace\cyberWife
# 按 M1-01 → M1-12 顺序执行
# 每完成一项追加 M1-audit.md
# 任一 AC-M1-XX 失败立即停手
```
