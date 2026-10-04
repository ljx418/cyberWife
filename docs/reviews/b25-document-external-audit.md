# B2.5 外部文档审计与闭环

**日期**：2026-09-25  
**审计工具**：Claude Code CLI 2.1.205，只读模式，Read/Grep/Glob  
**审查包**：12份Markdown + 1份Draw.io；少于20份  
**状态**：PASS；第二轮复审确认开放 P0/P1=0，可进入 B2.5 O1

## 1. 首轮独立结论

外审对以下八项给出结论：阶段依赖 PASS；跨文档语义 PASS；事实与目标分层 PASS；OX-01～12 四要素 PASS；硬件与时延数字一致 PASS；缓存防污染设计 PASS；迁移回退 PASS；代码实体一致性 PARTIAL PASS。

首轮提出 1 个 P1 和 6 个 P2。

## 2. 意见复核

| ID | 原意见 | 复核证据 | 处置 |
|---|---|---|---|
| P1-01 | `workers/speech_worker/server.py` 不存在，却标为已开发 | 文件实际存在；`ls -l`可见；`import workers.speech_worker.server`成功；B0/B1真实报告已使用8091 | **误报，关闭**。不修改正确的“已开发”状态 |
| P2-01 | `TurnPipeline`、`LiveTalkingAdapter`、Speech server仍列“必须新增” | 三文件均存在并可导入 | **有效，已修订** `backend-development-plan.md §3.2/3.3` |
| P2-02 | 未核验 `implementation-contracts.md §16/§27` | §16标题为“错误码目录与user_action枚举”；§27为“deadline完整表” | **已验证，引用准确，关闭** |
| P2-03 | B2.5计划顶部应明确代码授权边界 | 顶部状态已改为架构获准、外审闭环中、代码尚未开始 | **已修订** |
| P2-04 | `DOC-G0～DOC-G5` 未展开 | PRD路线图已展开为需求、架构、验收、追踪、风险、审批 | **已修订** |
| P2-05 | 七阶段与原六阶段计数口径不同 | `global-development-status.md` 已明确原计划2/6、加入B2.5后2/7 | **可接受，已解释** |
| P2-06 | 内审声称Speech server存在与P1冲突 | P1为外审工具漏检；已补文件与Python导入证据 | **误报同源，关闭** |

## 3. 独立事实证据

```text
backend/cyberwife/application/turn_pipeline.py          存在，可导入 TurnPipeline
backend/cyberwife/adapters/live_talking_adapter.py      存在，可导入 LiveTalkingAdapter
workers/speech_worker/server.py                         存在，可导入 workers.speech_worker.server
docs/implementation-contracts.md §16                    错误信封与错误码目录
docs/implementation-contracts.md §27                    deadline完整表
```

## 4. 当前判定

首轮所有有效意见均已落盘；唯一 P1 经直接文件与导入证据判定为误报。复审必须再次检查：

1. 上述三实体状态与后端计划分类；
2. B2.5命名无残留；
3. 阶段顺序无死锁；
4. 普通链与缓存命中统计隔离；
5. 外审闭环后才把计划状态提升为可开发。

## 5. 第二轮复审结论

Claude Code 第二轮按精确路径直接读取三实体与修订文档，确认：

- `TurnPipeline`、`LiveTalkingAdapter`、`workers/speech_worker/server.py` 均存在且与“已开发/需修改”状态一致；
- `implementation-contracts.md §16/§27` 引用准确；
- B2.5 命名无残留，阶段顺序无死锁；
- 普通路径与缓存命中统计隔离成立；
- 没有新增 P0/P1/P2。

最终判定：**PASS，开放 P0/P1=0**。依据用户“重新命名为B2.5，然后继续执行后续开发计划”的明确授权，可进入 O1。O1 仅允许计量与证据能力，禁止引入 TensorRT、vLLM、WarmResponseCache 或切换默认 TTS。
