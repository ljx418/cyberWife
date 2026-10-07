# UX15 阶段结果

**日期**：2026-10-07
**结论**：AUTOMATION PASS / UX15-AC05 HUMAN PENDING

## 已完成

- 完整场景循环Idle改为常驻安全底层。
- Intro/Outro改为就绪后才显示的一次性叠加层，换源不再制造空窗。
- 实时Canvas退出时先交还Idle并延迟260ms清理最后帧；快速新帧会取消旧清理任务。
- 序列故障、Avatar降级、stale/portrait画布继续失败关闭，不影响语音主链。

## 自动化证据

- 前端生产构建PASS；Playwright 24/24；人工报告核心3/3。
- 后端375 passed/7 skipped；根验收56/56；Avatar 16/16。
- Headless真实Gateway取证：循环Idle opacity=1、Intro叠加层opacity=1、Canvas complete-scene且未live时opacity=0；页面始终由完整场景覆盖，无矩形人物层。
- Canvas像素测试确认stop后淡出窗口内最后帧仍保留，260ms后才清理。

## 保留人工门

请在强制刷新后的同一浏览器连续执行3次“开始对话→结束对话”。只有人工确认无闪动、黑帧、遮罩或第二人物，UX15-AC05才可签PASS并进入V1人工总验收。
