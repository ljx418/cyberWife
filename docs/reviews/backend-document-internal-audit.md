# V1 后端文档内部审查报告

**日期**：2026-09-24  
**审查范围**：G-UX 批准后的后端文档重基线  
**结论**：文档已具备指导 DEV-B0～DEV-B5 自动化开发的结构和硬门槛；当前等待人类审查新版 Draw.io，尚未授权产品代码开发。

## 1. 第一轮：代码事实与架构一致性

### 发现并修复

1. 旧架构图把后端整体描述为“未开发”，与仓库事实冲突。新版按“可复用/需修改/待新增/阻断”重新标注。
2. `ApiGateway` WebSocket 实际只回 ack，旧文档容易把“端点存在”误读为实时链完成。新版明确列为阻断。
3. `HealthAggregator` 当前按模型清单推断 ready，VRAM/RAM 为空。新版规定只有 functional probe 可以产生 ready。
4. `RuntimeLauncher.ps1` 传给 Gateway 的 `--config` 参数不存在，LLM 健康检查错误使用 `/api/v1/health`，且只覆盖 Gateway/LLM。新版把修复列为 B0 第一优先级；9KB `llama-server.exe` 后经 `--version` 证实为薄启动器，不再按体积误判 stub。
5. `ConversationOrchestrator` 已有六态和 event_seq，但没有 async pipeline 与统一取消。新版拆出 `TurnPipeline` 和 `InterruptionController`，避免让领域对象持有 GPU task。
6. CosyVoice 的显存优势曾被误当成切换理由。新版固定 Qwen 默认，Cosy 走不阻塞 V1 的独立候选门。

### 判定

通过。目标实体均可映射到当前文件或明确的新增路径；没有用抽象名掩盖实际实现责任。

## 2. 第二轮：PRD、计划与验收追踪

自动检查结果：

- FR-01～FR-19：追踪矩阵全部覆盖；
- NFR-01～NFR-10：追踪矩阵全部覆盖；
- AC-01～AC-14：验收计划全部存在；
- B0～B5：开发计划全部存在且有用户效果、任务和出门门；
- 核心 7 份 Markdown 的本地链接：0 个失效；
- Draw.io：XML 可解析，共 8 页，符合上限；
- Archify：showcase 校验 9/9、composition 0 error/0 warning；宿主 Chrome 1600×1000 手工截图完成视觉检查。内置 `visual-check` 因 WSL→Windows Chrome debugging-pipe 不兼容未形成自动浏览器收据，该环境限制不影响规格校验结论；
- 后端现有回归：`221 passed, 4 skipped`，耗时 22.39 秒。

### 判定

通过。每项 Must 需求至少连接一个代码责任、开发里程碑和可执行验收。前端 G-UX 批准被记录为范围冻结，但 AC-11 仍要求真实后端接线后的回归，没有把设计批准冒充产品完成。

## 3. 第三轮：失败模式与出门风险

| 风险 | 失败表现 | 文档控制 | 剩余不确定性 |
|---|---|---|---|
| llama-server 为 stub | B0 无法真实启动 LLM | B0-03 阻断门、真实 token probe | 需要实施时获取可运行发行件 |
| WSL/Windows 生命周期错位 | 启停残留、错误杀进程 | PID 所有权、回滚、有序停机、幂等 AC-14 | PowerShell 真机行为只能实施期验证 |
| event loop 被 GPU 阻塞 | 首响恶化、无法打断 | worker/process、有界队列、deadline | 需实际 profile 决定线程/进程参数 |
| 多模型组合超资源 | OOM 或系统换页 | VRAM≤22GB、项目RAM≤14GB、MemAvailable/swap每分钟曲线 | B0已完成短时组合测量；B3补1小时 |
| Avatar 上游耦合 | 版本变化导致接口断裂 | `AvatarPort` 防腐层、pinned revision、合同测试 | 上游 WebRTC 行为需真机验证 |
| CosyVoice 内容错误 | 声音可生成但语义错 | 独立候选门，不允许替换 Qwen | 根因尚未定位，不影响主线 |
| 删除只删 UI/源表 | 语义检索仍召回 | 单事务覆盖 source/FTS/vector/cache，故障注入 | sqlite-vec 事务行为需实现验证 |
| no-record 补偿不完整 | 会话前半段残留 | 策略置于持久化入口并补偿删除 | 崩溃窗口需实现期测试 |

### 判定

风险不能在文档阶段归零，但均已有明确触发信号、默认路线、停线条件和验收证据，不再需要实施 Agent 临场做产品级选择。

## 4. 架构路线对比

| 路线 | 优点 | 缺点 | 结论 |
|---|---|---|---|
| 模块化单体 + 本机进程 | 复用现有代码、事务简单、低运维、可取消 | Gateway 影响面较大，跨 WSL 探针复杂 | V1 采用 |
| 全部拆微服务 | 独立扩缩容与故障隔离 | 单用户本机过度复杂，测试/部署成本大 | 拒绝 |
| Docker 前移 | 环境一致 | 与 V1 范围冲突，GPU/网络/卷增加风险 | 留 V2 |
| Qwen 默认 | 当前内容正确率证据最好 | 显存较高，首包仍需测 | V1 采用 |
| CosyVoice 默认 | 显存较低 | CER 76.92%、首包 10.043s | 当前拒绝，仅候选 |

没有需要用户在开发前再次选择的技术分叉；如果 CosyVoice 后续过门，再以 ADR 单独决策。

## 5. 文档落盘检查

待审核心文档共 10 项，小于 20：

1. `docs/PRD.md`
2. `docs/experience-benchmark.md`
3. `docs/backend-development-plan.md`
4. `docs/project-plan.md`
5. `docs/architecture/target-architecture.md`
6. `docs/architecture/backend-v1-architecture.html`
7. `docs/acceptance-plan.md`
8. `docs/traceability-matrix.md`
9. `docs/implementation-contracts.md`
10. `docs/cyberWife-architecture-gap.drawio`

辅助证据包括 `docs/M3-cosyvoice-validation.md`、`docs/model-manifest.md` 和 `docs/review/assets/`，不作为主审文档重复提交。

## 6. 内审最终结论

- 规格偏移风险：低。G-UX 冻结、FR/NFR/AC 和 B0～B5 已追踪。
- 架构不可实施风险：低到中。实体和合同明确；真实跨进程行为留实施验证。
- 验收不可判定风险：低。场景、操作、采样口径、量化门槛和证据均明确。
- 目标失败风险：仍为中。主要来自真实模型组合、跨 Windows/WSL 和 Avatar 性能，而不是文档缺口。

建议：由人类先审查 8 页 Draw.io 是否存在方向偏移或过度承诺；批准后进入外部文档审查。外审通过且用户明确授权产品开发后，从 DEV-B0 开始，不跳过真实启动基线。
