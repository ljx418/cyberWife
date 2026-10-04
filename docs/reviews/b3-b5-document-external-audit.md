# B3—B5 外部文档审查与闭环

**日期**：2026-09-25  
**审查工具**：Claude Code CLI 2.1.205，`--permission-mode plan`，两轮独立只读审查  
**最终结论**：P0=0、P1=0；建议允许进入人类开发批准门。B3—B5 仍为 `NOT EXECUTED`。

## 1. 审查范围（19项）

`PRD.md`、`prototype-spec.md`、`target-architecture.md`、`implementation-contracts.md`、`backend-development-plan.md`、`project-plan.md`、`acceptance-plan.md`、`acceptance-command-manifest.md`、`traceability-matrix.md`、`model-manifest.md`、`global-development-status.md`、8页 Draw.io、交互评审 HTML，以及 B3/B4/B5 的 plan 与 acceptance。

## 2. 第一轮结论与处置

第一轮给出 P0=6、P1=9、P2=7，并建议修订后再审批。其中 P0-1“缺少 AC-04A 定义”为误报：`acceptance-plan.md` 原已包含场景、前置、步骤和硬门。

有效发现已全部修订：

- 新增 `acceptance-command-manifest.md`，固定未来 runner、退出码、证据 schema 和资源采样；明确当前不存在 runner、不得以占位脚本过门。
- 新增 B5-AC00，不完成授权/资产版本/人设/默认入口/六类设置 API/HostBridge 合同，不得进入组合回归。
- 澄清 16GB 启动前可用、14GB 项目峰值、≥2GB 双侧安全线和 B2 0.3GiB 快照之间的关系。
- 对账 §26 历史风险接受与现行 NFR-04/NFR-06；后端日志/Git/音频/业务数据发布硬门不放宽。
- 固定低磁盘测量卷、触发范围与“不自动删用户数据”边界。
- 固定 CosyVoice→Qwen 回退所有者、触发窗口、禁止双常驻和人工恢复，避免震荡。
- 增补 B3.0 媒体 source 注册表、双时钟语义与 feature flag 迁移；B4 no-record ID 无痕、sqlite-vec 改造前后证据；网络允许集合和 schema 迁移合同。
- 追踪矩阵升级 v2.4，增加 AC→FR 反向索引；Draw.io 与 HTML 同步风险和状态表达。

## 3. 第二轮逐项判定

| 组别 | 结果 |
|---|---|
| 首轮 P0-1 | INVALID（原文已有 AC-04A） |
| 首轮 P0-2～P0-6 | CLOSED |
| 首轮 P1-1～P1-9 | CLOSED |
| 新增 P0/P1 | 0 / 0 |
| 命令清单真实性 | PASS：足以指导未来实现，未伪报脚本存在 |
| 语义连贯性 | PASS：PRD、架构、阶段依赖、隐私、资源、磁盘、回退和状态一致 |

第二轮保留 7 个 P2，均为索引/可读性或在主合同已有间接引用，不阻断开发授权。首次签署 V1 Go 时，任何仍开放 P2 只能在用户书面接受且有绕行方案时保留。

## 4. 审查文件与真实性边界

CLI 原始报告位于本机：

- 首轮：`/home/administrator/.claude/plans/v1-19-docs-prd-md-docs-prototype-spec-m-modular-parnas.md`
- 二轮：`/home/administrator/.claude/plans/home-administrator-claude-plans-v1-19-d-structured-barto.md`

CLI 只读审查未运行 B3—B5 产品验收。外审“PASS”只代表文档可进入人类开发批准门，不代表 B3、B4、B5 或 V1 产品通过。

## 5. 最终审批建议

建议允许下一次明确授权后进入 B3 实际开发。B3 启动必须先按命令清单 §6 创建 runner 合同测试与证据 schema；每个子阶段仍执行计划→开发前审计→实现→真实 E2E→PRD 检视。任何硬门失败必须回到计划阶段，不得降低门槛。
