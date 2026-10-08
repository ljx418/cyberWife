# V2-X0.3 自动化验收报告

**自动化结论**：X03-AC01～07 PASS  
**V2X-AC11真实声场部分**：PENDING HUMAN

| 证据 | 结果 |
|---|---|
| 0/50/100音量、静音与恢复 | Gain参数即时更新，取消静音恢复原音量 |
| 当前回答重播 | PCM仅内存；重播不增加播放遥测、不调用Avatar |
| 新turn/打断/取消/结束 | 重播source停止，缓存字节归零 |
| 有界缓存 | 小上限确定性测试证明超限后chunks=0、bytes=0、overflowed=true |
| 输出设备 | 能力存在时调用`setSinkId`；缺失时返回`unsupported` |
| feature flag | 开启显示控制；关闭完全隐藏；无历史语音库入口 |
| 前端全量 | build PASS；Playwright 36/36 PASS |
| 后端全量 | pytest 393 passed、7 skipped；无新增失败 |

自动化能证明控制、释放、缓存边界和降级合同，但不能替代真实扬声器上的压缩听感、设备路由和音画同步主观检查；该部分保留到G-V2X前的人类门。
