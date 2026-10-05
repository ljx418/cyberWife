# V1RC1 发布冻结

**日期**：2026-10-06
**自动化候选结论**：PASS
**V1总发布结论**：CONDITIONAL

## 冻结实现

- 普通话简体ASR归一；整句最终回复仅一次CosyVoice推理。
- Prompt一条自然短句/18字目标，LLM生成上限48 token。
- RuntimeLauncher默认解析持久化active avatar，显式参数仍优先。
- CosyVoice2每轮恢复冻结初始流式hop窗口；系统可用内存3GiB/Gateway RSS4GiB双门回收arena。
- 20/30/60分钟runner均读取真实active avatar并记录协议，不再由心跳版本覆盖视频协议。

## 冻结证据

- `audit/v1/V1RC1/R1-AC02-20turn/`
- `audit/v1/V1RC1/AC05-R2-normal30/`
- `audit/v1/V1RC1/AC04-interrupt30/`
- `audit/v1/V1RC1/AC04-generation-fence/`
- `audit/v1/V1RC1/AC05-release60m-rerun/`

## 最终自动化回归

- 后端：356 passed，5 skipped。
- 根验收：21 passed。
- Avatar worker：13 passed。
- 前端：production build PASS，Playwright 15 passed。
- PowerShell AST、Draw.io 8页XML、diff whitespace检查：PASS。

## V1FINAL接续

V1RC1之后已建立`docs/stages/V1FINAL/`。Narrator、结构化物理麦克风和UX6当前Crop V2感知统一由headed Chrome现场验收器处理：机器自动绑定PCM、三轮、打断、接续、active avatar和Idle，人类只签读屏/口型自然度，且报告不保存正文或音频。干净Windows+WSL整机安装仍是独立开放门；没有现场/新环境证据不得冒签。
