# UX1 开发前审计

- 致命/重大规格偏差：0。
- 已确认根因：`active_assets` 与 `RuntimeLauncher --avatar_id` 之间没有派生物或运行时寻址合同；`AvatarSession` 使用 `alpha:false` Canvas，清空后仍覆盖写真；CSS 使用固定 `cover` 焦点。
- 技术边界：本子阶段不引入新常驻模型，不改变音频主时钟，不突破 RAM/VRAM 门。
- 审计结论：允许进入实质开发；任何 SHA 不一致、黑屏或路径逃逸测试失败均退回本计划。

