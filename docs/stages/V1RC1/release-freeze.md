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

## 不得冒签的外部门

Narrator人工听感、结构化物理麦克风ACC1、干净Windows+WSL整机安装、UX6当前Crop V2完整口型/Idle主观评分仍为开放门。自动化开发在这些门前正常停止；后续只需人类/独立环境签署或基于签署反馈建立新的修复阶段。
