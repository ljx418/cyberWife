# cyberWife V1RC1 阶段性独立审计

**审计日期**：2026-10-06
**候选范围**：UX7普通话/整句口播、R3首包窗口复位、AC05-R2 RAM双门
**结论**：工程候选自动化门全绿；V1总发布仍为CONDITIONAL。

## 当前候选真实证据

- Windows Chrome普通链30/30，P50/P95=4.102/4.708秒，缓存命中0。
- 早/中/晚打断各10次，30/30，用户可听静音P95=1.9ms，旧generation泄漏0。
- Generation fence PASS：取消轮DB冻结，真实第二轮ASR/LLM/TTS完成。
- 60分钟：20完整+10打断、721资源样本，RAM峰值13,775.637MiB，VRAM峰值11.219GiB，后30分钟RAM斜率0.390333MiB/min。
- 当前人物为 `wav2lip256_idle_p_7ecfeecee271a502_47cbb203_cropv2`，协议v2；60分钟89,981帧。
- 生命周期：start幂等、Avatar单项恢复、stop×2与端口/PID归零均PASS。

## 白盒结论

CosyVoice2冻结上游把流式 `token_hop_len` 从25增长到100后跨请求保留。适配器在每轮推理前恢复冻结初值，仅保留单轮内部增长；首响P95由失败批次7.727秒降至4.708秒。完成轮次后以系统余量<3GiB或Gateway RSS>4GiB触发arena trim，使延迟与14GiB RAM门同时成立。未修改模型权重、音色、整句策略、采样率或协议。

## 自动化覆盖

最终冻结回归已完成：后端356 passed/5 skipped、根验收21 passed、Avatar worker 13 passed、前端生产构建与Playwright 15 passed；PowerShell AST、8页Draw.io XML和`git diff --check`通过。

## 仍需外部签署

1. Narrator真实播报五项任务的人工听感。
2. 物理麦克风按ACC1脚本完成至少三轮、一次打断与接续的正式签字（用户已有真实交互反馈，但不冒充该结构化门）。
3. 全新Windows用户+干净WSL+驱动+本地模型工件的独立整机安装复现。
4. UX6当前Crop V2在完整实时对话中的口型、嘴部与Idle主观评分。

因此自动化可完成的开发计划已实现并重签，但没有权限把上述外部环境/人类感知门写成PASS。
