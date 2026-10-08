# V2-X9 自动化验收报告

**自动化结论**：X9-AC01～08 PASS  
**V2X-AC15目标机部分**：PENDING HUMAN

| 证据 | 结果 |
|---|---|
| Manifest与图标 | 公开请求成功；name/start_url/scope/standalone及192/512图标完整 |
| 安装事件 | `beforeinstallprompt`只触发一次prompt；接受后状态清晰 |
| Fullscreen API | 进入/退出由`fullscreenchange`驱动，按钮状态一致 |
| 实际Cache Storage | 仅`cyberwife-public-shell-v1`；页面壳/manifest/内置背景可命中 |
| 缓存禁区 | `/api/`与带Authorization请求命中为0；源码同时拒绝WS和私有媒体路径 |
| feature flag | 关闭后桌面控制为0，开始对话与设置入口保持可达 |
| 偏好回归 | 既有背景跨刷新用例通过，localStorage键未迁移 |
| 前端全量 | build PASS；Playwright 40/40 PASS（4 workers） |
| 后端全量 | pytest 393 passed、7 skipped；无新增失败 |

自动化没有代签Chrome菜单中的“安装应用”、Windows桌面图标、standalone窗口和系统重启恢复；这些属于V2X-AC15目标机人工证据。
