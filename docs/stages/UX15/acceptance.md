# UX15 验收标准

| ID | 用户操作 | 自动化证据 | 出门门槛 |
|---|---|---|---|
| UX15-AC01 | Idle状态点击开始对话 | Headless DOM/CSS状态序列 | live首帧前循环Idle保持可见；首帧后Canvas与Idle交叉淡化；不存在全透明时刻 |
| UX15-AC02 | live状态点击结束对话 | Headless DOM/CSS状态序列 | Canvas退出时循环Idle立即接管；Outro仅就绪后叠加；不卸载循环Idle |
| UX15-AC03 | Intro/Outro加载失败 | 故障注入 | 对话功能不受阻；循环Idle持续可见；无黑屏、旧写真或portrait遮罩 |
| UX15-AC04 | 完整回归 | build、Playwright、pytest | V1既有自动化门全绿；P0/P1新增回归为0 |
| UX15-AC05 | 人工连续操作 | 同一浏览器连续开始/结束3次 | 人工确认无可感画面闪动后，进入V1人工总验收 |
