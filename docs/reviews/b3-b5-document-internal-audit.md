# B3—B5 文档内部独立审计

**日期**：2026-09-25  
**范围**：B3 全双工打断、B4 记忆/隐私/保留、B5 规格补齐与 V1 总验收  
**结论**：三轮审计后 P0=0、P1=0；文档足以进入外部审计，但不代表任何 B3—B5 产品功能已实现或通过。

## 第一轮：PRD 规格与体验闭包

方法：逐项核对 PRD 的 FR-01～20、NFR-01～10、AC-01～14/AC-04A 与追踪矩阵、阶段计划、验收步骤和交互原型。

- FR-01～20 与 NFR-01～10 在追踪矩阵中均有代码实体、阶段、验收项和当前事实。
- B3、B4、B5 各自具备“用户场景、用户操作、可观测证据、量化门槛、失败动作”，不存在三无验收章节。
- 用户路线覆盖首次设置、日常多轮、插话纠正、记忆与不记录、故障恢复、退出与数据；没有增加云端、桌面壳或超出 V1 的能力。
- 当前默认旧入口与已批准沉浸式页面的差异被保留为 B5 明确缺口，没有用原型冒充实现。

本轮发现并修复：旧体验基线仍写 CosyVoice 不得默认；已改为 ADR-008 的 CosyVoice 默认/Qwen 显式回退事实。结论：P0=0、P1=0。

## 第二轮：架构、接口与语义一致性

方法：从浏览器输入沿 `ConversationClient → ApiGateway/SessionRuntime → TurnPipeline → adapters → MediaSession/AvatarSession → Repository` 双向走查，并核对阶段依赖和资源边界。

- B3 固定为持续 receiver、单 active turn、有界 outbound queue、单 sender；取消由 generation fence 覆盖字幕、音频、帧和持久化，400ms 听感门与 1000ms 回收门分离。
- B4 固定使用 FTS5 + sqlite-vec + BGE 512维，索引不可用 fail-closed；MemoryRepository 是唯一事务所有者；no-record 的创建态与会话中切换均可验证为业务零增量。
- B4 入口固定为 B3 `e2e_accepted`，避免用 mock session 验记忆；B5 入口固定为 B3/B4 PASS。
- B5 先补授权、资产版本、人设和默认入口，再运行全集；测试文件存在不能替代功能实现。
- CosyVoice 默认非 TRT FP16 流式，Qwen 回退；不双常驻。项目 RAM≤14GB、VRAM≤22GB、宿主/WSL 可用内存各≥2GB，未恢复 28GB 要求。

本轮发现并修复：原型将 FTS5/sqlite-vec 误写为 FTS6/Vector4；旧资源注释仍称 Qwen 为当前默认；均已统一。结论：P0=0、P1=0。

## 第三轮：证据真实性与可执行性

方法：结构解析、链接检查、浏览器自动化、图形导出和代码基线哈希复核。

- Draw.io XML 可解析，恰好 8 页；Windows draw.io 成功导出 8 页 PNG 与 8 页 PDF，抽查架构、B3、B4、验收页可读。
- 23 份主动文档的本地 Markdown 链接缺失数为 0；交互 HTML 的 6 个本地资源引用缺失数为 0。
- Windows Chrome 实测原型：B3 `INTERRUPTED`、不记录确认、删除确认、Tab 焦点循环、Escape 关闭和浅/深主题均可操作；控制台错误为 0。
- 浏览器自动化曾发现 no-record 回调错误使用失效的 `event.currentTarget`；已改为稳定元素引用并复测通过。
- 420×820 真实 CSS 视口：`scrollWidth=405 ≤ innerWidth=420`；页面无横向溢出。当前默认实现的 1920×1080 截图已落盘。
- B3/B4/B5 验收与 PRD 检视均明确标记 `NOT EXECUTED`；没有提前签署产品 PASS。
- 文档修改前后产品范围 `backend/`、`prototype/src/`、`workers/`、`ops/` 共 307 个文件的组合 SHA256 均为 `b0f22a5bf4416521e95a39c5ddc5c80c263ab5d2a0f048f9806342d81911267c`，证明本阶段未修改产品代码。

结论：P0=0、P1=0；原型缺陷已闭环。允许进入外部文档审计，不允许据此进入产品开发。

## 外审输入清单（19 项）

1. `docs/PRD.md`
2. `docs/prototype-spec.md`
3. `docs/architecture/target-architecture.md`
4. `docs/implementation-contracts.md`
5. `docs/backend-development-plan.md`
6. `docs/project-plan.md`
7. `docs/acceptance-plan.md`
8. `docs/traceability-matrix.md`
9. `docs/model-manifest.md`
10. `docs/global-development-status.md`
11. `docs/experience-benchmark.md`
12. `docs/cyberWife-b3-b5-delivery-gap.drawio`
13. `docs/review/cyberwife-v1-b3-b5-delivery-review.html`
14. `docs/stages/B3/plan.md`
15. `docs/stages/B3/acceptance.md`
16. `docs/stages/B4/plan.md`
17. `docs/stages/B4/acceptance.md`
18. `docs/stages/B5/plan.md`
19. `docs/stages/B5/acceptance.md`

## 保留风险

- B3 的真实 30 次打断/100轮/1小时结果仍未知；失败时必须返回 B3 计划，不得放宽 400ms 听感门。
- sqlite-vec 与 BGE 在 16GB 空闲预算下的真实并存结果仍待 B4 测量；失败时可调整生命周期，不能用 FTS-only 冒充。
- B5 授权、资产版本和默认入口是真实开发缺口；未补齐前禁止把全量回归标为 V1 GO。
- Wav2Lip 许可证仅限研究用途，V1 只面向用户批准的本机私人研究；用途变化必须重新评审。

## 外审后复核

Claude Code CLI 首轮外审提出的有效 P0/P1 已全部纳入合同；第二轮逐项复审判定 P0=0、P1=0，详见 [`b3-b5-document-external-audit.md`](b3-b5-document-external-audit.md)。首轮“缺少 AC-04A”被确认是误报。内部结论更新为：文档可以进入人类开发批准门，产品开发仍未获本轮授权、仍未开始。
