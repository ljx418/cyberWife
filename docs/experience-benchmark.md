# V1 交互体验对齐与 G-UX 验收基线

**状态**：G-UX 已获人类批准；B3—B5已实现，本文保留为体验基线，最新验收边界见阶段审计  
**当前交付评审页**：[`review/cyberwife-v1-b3-b5-delivery-review.html`](review/cyberwife-v1-b3-b5-delivery-review.html)  
**历史 G-UX 原型**：[`review/cyberwife-v1-experience-review.html`](review/cyberwife-v1-experience-review.html)

## 1. V1 体验结论

V1 的核心不是“能调用若干模型”，而是本地一键启动后直接进入稳定的陪伴主舞台：用户自然开口、系统尽早回应、可随时打断，并能在无限多轮中保持可理解的状态、可控的记忆和明确的隐私边界。

默认视觉方向为 **Cinematic**：深靛背景、暖琥珀关系色、低噪声控件、人物优先。Quiet 与 Signal 仅作为本轮评审对照，不构成 V1 多主题交付承诺。

## 2. 当前真实基线

| 项目 | 当前事实 | V1 差距 |
|---|---|---|
| 前端入口 | `prototype/src/App.tsx` 已成为生产默认主舞台，Gateway在API/WS之后托管构建产物 | 已通过静态入口与API优先级回归 |
| 移动端 | 420×720无横向溢出，设置抽屉可滚动 | 自动化覆盖布局/axe；完整任务与触控仍需人工复核 |
| 实时链路 | 已实现可取消全双工接管、30次打断与Avatar恢复 | 授权WAV覆盖充分；真实物理麦克风和A/V偏移量仍待测 |
| 启动 | 目标机start/status/recover/stop与双击入口已通过 | 干净机安装尚未验收 |
| 自动化 | 后端326 passed/4 WSL跳过；Avatar9、根验收4、Playwright9通过 | 测试套件仍需统一根入口；自动化子集不替代真实读屏 |
| TTS | 固定正确逐字稿30条：Qwen CER 2.14%、CosyVoice CER 0.71%；V1RC1 Windows Chrome普通链30/30，首响P50/P95=4.102/4.708s；60分钟RAM/VRAM/趋势达门 | CosyVoice2按ADR-008保持默认非TRT FP16；R3复位跨请求hop窗口，AC05-R2以系统余量/RSS双门回收；Qwen保留回退 |

基线截图与真实音频均保存在 `docs/review/assets/`，来源记录见 `docs/review/assets/source-manifest.json`。

## 3. 用户路线契约

- **J-01 首次见面**：同意与数据边界 → 运行时自检 → 肖像/声音/人设 → 进入陪伴。
- **J-02 日常聊天**：一键启动 → 自然开口 → 流式回应 → 持续多轮且资源稳定。
- **J-03 打断纠正**：回答中检测新语音 → 取消旧 turn → 清空播放缓冲 → 新 turn 接管。
- **J-04 故障降级**：发现异常 → 保护当前会话 → 提供重试/降级/诊断 → 无重复播放地恢复。

## 4. G-UX 出门条件（已批准）

人类已在交互原型中逐项审查并明确批准：

1. Cinematic 主舞台的关系感、人物占比、信息密度和默认色彩；
2. idle/listening/thinking/speaking/interrupted/degraded 的表达和操作；
3. 设置、记忆、隐私、错误恢复组件的功能边界；
4. J-01 至 J-04 没有遗漏或超出 PRD 承诺。

G-UX 已完成，B3—B5也已进入实现与目标机验收。当前不得把阶段历史PASS外推为全部用户场景全绿；最新缺口以`review/2026-10-04-stage-audit.md`为准。

## 5. 不构成已实现的内容

原型中的实时遥测、状态切换、记忆编辑、导出与删除均为交互契约演示。AI 概念图不是当前产品截图，参照项目公开的首响与 FPS 描述也不是本机验收证据。后续所有 V1 出门结论必须来自目标硬件上的可重复端到端记录。
