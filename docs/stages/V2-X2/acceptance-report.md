# V2-X2 自动化验收报告

**自动化结论**：X2-AC01～07 PASS（可自动化范围）  
**V2X-AC02真人脸部安全区**：PENDING HUMAN

| 证据 | 结果 |
|---|---|
| 控制器 | standard/ultratall/strip分类、焦点clamp、条幅降级确定性通过 |
| 构图切换 | 近景/半身/全身可选；全身跨刷新保留 |
| 2160×3500 | 全身有效；背景填满、无横向溢出、主操作可达 |
| 420×720 | 全身有效；背景填满、无横向溢出、主操作可达 |
| 3840×180 | requested=full、effective=close；降级说明与开始对话均可见 |
| flag关闭 | 构图控制隐藏，已存full被忽略，使用V1 half |
| 单人物白盒 | 未改AvatarSession/MediaSession，未新增媒体层 |
| 前端全量 | build PASS；Playwright 48/48 PASS（4 workers） |
| 后端全量 | pytest 398 passed、7 skipped；无新增失败 |

自动化验证DOM边界、背景覆盖、溢出和控制可达；具体真人脸框是否达到审美安全区仍需用最终活动素材截图人工确认。
