# cyberWife V1 阶段性独立审计

**审计日期：** 2026-10-04  
**审计基线：** `docs/PRD.md` v1.8、`docs/architecture/target-architecture.md` v2.4  
**权威架构图：** `docs/cyberWife-b3-b5-delivery-gap.drawio`（8页）  
**结论：** **阶段验收不通过 / V1 发布阻断；工程候选保留，非全绿。**

## 1. 一句话判断

当前实现已经具备本机真实模型对话、流式语音、Avatar 输出、插话取消、记忆与隐私控制和一键生命周期主体能力；但是本轮60分钟目标机复验因 Windows 可用内存最低1,840.566MiB低于2GiB硬门而返回FAIL。加上目标架构依赖方向、完整真实读屏旅程、真实物理麦克风、口型同步量化、全新机器安装五项证据缺口，不能把“工程链路可运行”写成“V1 全部出门条件全绿”。

## 2. 审计方法与证据等级

| 等级 | 含义 | 本轮用途 |
|---|---|---|
| E1 白盒证据 | 源码、配置、依赖、静态扫描、单元/集成测试 | 判断功能实体、分层、隐私边界和测试覆盖 |
| E2 Headless 证据 | Playwright/Chromium 无头浏览器、axe、响应式与截图 | 验证页面合同、交互状态、键盘与布局；截图 API 为确定性桩，不作为模型运行证据 |
| E3 目标机证据 | Windows 11 + WSL2、真实模型、真实资源采样 | 验证 LLM/ASR/TTS/Avatar、首响、打断、长稳和生命周期 |
| E4 人工感知证据 | 真实读屏、真人盲听、真实麦克风、口型主观/量化判断 | 仍有缺口；不得被 E1/E2 替代 |

本轮遵循用户已批准的网络验收替代方案：不物理断开 WSL 公网，以 loopback 绑定、出站白盒扫描和运行期连接采样验证。该替代不等价于物理断网，报告中不作等价宣称。

## 3. 本轮重新执行结果

| 检查 | 命令/方式 | 结果 | 证据等级 |
|---|---|---:|---|
| 后端单元与集成 | `PYTHONPATH=backend pytest -q backend/tests` | 326 passed，4 skipped（WSL 内无 PowerShell） | E1 |
| B3/B5 根验收测试 | 分离执行 `tests/b3/test_accept_soak.py`、`tests/b5/test_release_freeze.py` | 4 passed | E1 |
| Avatar 测试 | `workers/avatar` 中执行 pytest | 9 passed | E1 |
| 前端生产构建 | `npm run build` | 23 modules，PASS | E1 |
| 浏览器回归 | `npm run test:e2e -- --reporter=line` | 9 passed | E2 |
| PowerShell 语法 | Windows PowerShell AST 解析启动/停止/主机解析/总验收脚本 | PASS | E1 |
| 目标机 60 分钟真实组合 | `Invoke-V1ReleaseAcceptance.ps1` 独立证据目录 | **FAIL / exit 2**：20完整+10打断均PASS；Windows最低可用内存1,840.566MiB<2GiB | E3 |

说明：`backend/tests` 与根目录 `tests` 都使用顶层 Python 包名 `tests`，单进程合并收集时会发生模块遮蔽；按命令清单分开执行均通过。这是验收工具缺陷 P2，不是产品功能失败，但应在后续统一测试入口中修复。

## 4. PRD 用户旅程覆盖

| 用户旅程 | 已覆盖 | 本轮判断 | 仍缺什么 |
|---|---|---|---|
| J-01 首次设置 | 五步、草稿续接、授权门、运行检查、资产版本与回退 | 核心功能通过 | 全新 Windows+WSL 从安装到首次启动的独立复现 |
| J-02 日常对话与插话 | Chrome `getUserMedia` 虚拟麦克风注入授权真实WAV→ASR→LLM→TTS→Avatar、连续轮次、generation fence、插话静音 | 浏览器真实媒体与目标机模型链路通过 | 真实物理麦克风自由说话；可感知口型同步误差或主观评分 |
| J-03 记忆与隐私 | 召回、编辑、删除、全清、不记录、30天清理、loopback | 自动化覆盖较完整 | 用户批准的物理断网替代已记录，不再把它写成物理断网证据 |
| J-04 故障恢复 | 单服务降级、重试、原页恢复、重复 start/stop | 功能通过 | 干净机安装失败后的恢复演练 |

## 5. 目标架构与当前实现

| 目标实体/边界 | 当前实现 | 状态 | 审计判断 |
|---|---|---|---|
| 浏览器 UI → REST/WebSocket → Gateway | `prototype/src`、`application/api_gateway.py` | 已实现 | 绿 |
| `TurnPipeline` 串联 ASR/LLM/TTS/Avatar | `application/turn_pipeline.py` 与 adapters | 已实现 | 绿 |
| generation fence / 取消传播 / 有界队列 | B3 取消控制与媒体队列 | 已实现 | 绿 |
| SQLite + FTS + vector 的原子记忆控制 | repositories / memory service | 已实现 | 绿 |
| Windows launcher 管理 WSL 与 llama.cpp | `scripts/windows/*.ps1` | 已实现 | 黄：目标机已验，干净机未验 |
| UI→Application→Ports→Adapters→Infrastructure 单向依赖 | Application 仍直接导入 `SqliteRepository`、`AssetStore`、`StructuredLogger`、`RuntimeMetrics` | 未完全达成 | 黄：违反 NFR-07 目标依赖方向 |
| 浏览器可访问性完整任务 | axe、焦点圈闭、`aria-live`、减少动效 | 部分实现并自动化 | 黄：真实读屏及三视口全旅程未完成 |

具体分层偏差：

- `backend/cyberwife/application/api_gateway.py` 直接导入 `SqliteRepository`，并在处理函数中导入 `AssetStore`。
- `backend/cyberwife/application/turn_pipeline.py` 直接导入 `StructuredLogger` 与 `RuntimeMetrics`。
- 模型替换仍基本保持 adapter/config 边界，因此 NFR-07 判为“部分通过”，不是整体失败。

## 5A. 完整对话链记录

存在完整、可追溯的浏览器协议事件链证据。这里的“完整”指从媒体输入到播放结束/打断取消的控制链完整，不代表保存了可还原的逐字对话正文。按隐私设计，测试产物只记录正文 SHA-256、计数和事件顺序；没有保存明文逐字稿或授权音频。原始逐事件证据位于本机忽略目录 `audit/`。

代表性真实链来自 `audit/v1/B5/B5.4A-conversation-final/result.json`：Windows Chrome 通过标准 `getUserMedia`/AudioWorklet 注入授权真实 WAV，经真实 Gateway、ASR、LLM、CosyVoice 与 Avatar 完成。它记录 645 个输入二进制帧、0 个非法帧、4 个 `transcript.final`、4 个 `reply.text.final`、1630 个音频块、3 个完整播放、895 个 Avatar 解码帧；事件序列严格递增。浏览器停止前输入轨为 1，停止后输入轨为 0 且 AudioContext=`closed`。

完整控制事件链（正文仅保留 SHA-256）如下：

```text
seq 1     session     state.changed → listening (ws_connected)
seq 2     turn 1      transcript.final [hash]
seq 3     turn 1      state.changed → thinking
seq 7     turn 1      state.changed → speaking
seq 8     turn 1      reply.text.final [hash]
seq 593   turn 1      reply.audio.complete
seq 594   turn 1      state.changed → listening (playback_complete)
seq 595   turn 2      transcript.final [hash]
seq 596   turn 2      state.changed → thinking
seq 599   turn 2      state.changed → speaking
seq 600   turn 2      reply.text.final [hash]
seq 835   turn 2      barge_in.detected
seq 836   turn 2      turn.cancelled (barge_in)
seq 837   turn 3      transcript.final [hash]
seq 838   turn 3      state.changed → thinking
seq 841   turn 3      state.changed → speaking
seq 842   turn 3      reply.text.final [hash]
seq 1157  turn 3      reply.audio.complete
seq 1158  turn 3      state.changed → listening (playback_complete)
seq 1159  turn 4      transcript.final [hash]
seq 1160  turn 4      state.changed → thinking
seq 1164  turn 4      state.changed → speaking
seq 1165  turn 4      reply.text.final [hash]
seq 1664  turn 4      reply.audio.complete
seq 1665  turn 4      state.changed → listening (playback_complete)
```

链路边界：

1. 输入：Chrome `getUserMedia` → AudioWorklet → 16kHz/mono/PCM16 20ms 帧。
2. 理解：Gateway → VAD/ASR → `transcript.final` → generation 建立。
3. 生成：Prompt/Memory → llama.cpp 流式文本 → `reply.text.*`。
4. 发声：CosyVoice 非静音 PCM → 浏览器 AudioContext；首次播放确认回传 Gateway。
5. 形象：相同 PCM 送 Avatar → Wav2Lip → Annex-B H.264 → WebCodecs/canvas。
6. 打断：`barge_in.detected` → generation 作废 → LLM/TTS/音频源/Avatar队列清理 → 新 turn。
7. 收尾：`reply.audio.complete`/播放结束 → listening；结束会话释放媒体轨、AudioContext 与 WebSocket。

独立打断证据 `audit/v1/B5/B5.4C-AC05/result.json` 另记录早/中/晚各10次，共30/30通过，静音P95=2.6ms、旧generation音频=0、Avatar重连=0、decoder backlog=0。

本轮60分钟复验生成30个完整动作记录：20个`complete`与10个`interrupt`全部PASS；完整轮耗时6.884～14.882秒、事件数222～753，打断轮耗时4.968～6.181秒、事件数9～10。`actions.json`、721行资源样本、`manifest.json`与`lifecycle.json`均保存在`audit/v1/STAGE-AUDIT-20261004/AC14-full/`。该链路功能成功不能覆盖资源硬门失败。

## 6. 出门门槛

| 门槛 | 当前灯色 | 依据 |
|---|---|---|
| G1 功能完整 | 黄 | 四条主旅程主体完成；真实麦克风自由对话证据缺失 |
| G2 体验完整 | 黄 | 首响/打断/FPS达门；A/V 同步和真人感知未量化 |
| G3 隐私与本机边界 | 绿（批准替代） | loopback、出站扫描、运行期连接采样；未宣称物理断网 |
| G4 资源与长稳 | **红** | 60分钟、20完整+10打断、RAM/GPU/趋势达标，但Windows最低可用内存1,840.566MiB<2GiB；退出码2 |
| G5 架构一致 | 黄 | Application→Infrastructure 直接依赖仍存在 |
| G6 一键交付 | 黄 | 目标机 lifecycle 已通过；全新机器安装/引导未复现 |

**全绿判定：否。** 这些黄项不会否定当前目标机可用性，但阻止把候选版提升为“所有 V1 承诺均已验收”。

## 7. 测试覆盖完整性评价

自动化覆盖对状态机、取消栅栏、缓存、数据删除、一键生命周期、资源预算和故障注入较强；对人类感知与真实硬件入口较弱。当前用例能支持“目标机工程候选版”，不能完整覆盖 PRD 的所有用户场景。

建议关闭顺序：

1. 用物理麦克风完成首次设置后 20 轮自由对话，并保留浏览器事件与资源证据。
2. 对音频与 Avatar 帧建立共同时间戳，量化 A/V drift；追加 5 段真人主观口型评分。
3. 使用 NVDA 或 Narrator 在 1920×1080、1366×768、420×720 完成设置、开聊、插话、编辑人设、删除记忆。
4. 用新 Windows 用户或干净虚拟机执行安装→启动→恢复→卸载→数据清理。
5. 将 repository、asset store、logger、metrics 抽象为 ports 并增加架构依赖测试。

## 8. 文档一致性审计

- PRD、目标架构、项目计划、后端计划、追踪矩阵和命令清单已同步为“阶段验收不通过 / V1 发布阻断；工程候选保留”。
- B5 历史全绿报告保留原始签署语境，并添加“由本审计结论取代”的醒目说明，避免篡改历史证据。
- `docs/cyberWife-b3-b5-delivery-gap.drawio` 已同步真实实现、黄项和门槛，共 8 页，XML 可解析。
- 当前实现架构的可读版见 `docs/review/cyberwife-v1-stage-audit-architecture.html`。

## 9. 审计结论

**阶段性验收：不通过，发布阻断。** 工程候选可保留用于问题定位，但在G4红项以及G1/G2/G5/G6黄项关闭前，不得签署“V1全部开发与用户验收完成”。本结论优先于早期B5.6报告中的无条件PASS。自动化开发停止原因：独立60分钟复验触发Windows宿主可用内存硬门，继续追加模型负载会污染根因并增加OOM风险。
