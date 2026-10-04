# B2R Chrome 复验实施前审计

**日期**：2026-09-25  
**结论**：PASS，可执行只读环境检查与隔离 Chrome 真实复验

## 审计闭环

| 风险 | 闭环措施 | 状态 |
|---|---|---|
| 把 Chrome 的 offer 200 误判为媒体可用 | 强制检查 ICE/peer `connected` 与真实视频帧 | 已闭环 |
| 测试修改用户浏览器设置 | 使用测试专用 profile；参数仅作用于该进程 | 已闭环 |
| 候选泄漏本机地址 | 审计 JSON 只写 candidate 类型、协议和 mDNS/IP 分类 | 已闭环 |
| 为验证而修改全局 WSL/防火墙 | 本轮明确禁止；只读采集状态 | 已闭环 |
| 复验绕过产品协议 | 使用真实 `/offer`、真实 aiortc/Wav2Lip 服务和浏览器 WebRTC API | 已闭环 |
| A2 与现有音频链冲突 | 选型约束音频继续走 Gateway PCM，视频使用独立有界队列 | 已闭环 |

没有新增致命或重大规格偏差。复验失败只证明当前 Windows Chrome→WSL WebRTC 路径不可用于 V1，不等同于 Avatar 模型失败。
