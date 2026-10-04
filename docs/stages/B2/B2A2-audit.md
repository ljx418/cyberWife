# B2-A2 实施前审计

**日期**：2026-09-25  
**结论**：PASS，可进入 A2-1；开放致命/重大规格偏差=0

| 风险 | 约束与验证 | 状态 |
|---|---|---|
| 视频阻塞音频 | 独立 WebSocket；队列上限2；音频仍由 Gateway PCM 播放 | 已闭环 |
| H.264 分片不可解码 | 一消息一 access unit；Annex-B；关键帧含SPS/PPS；Chrome真实解码 | 已闭环 |
| 新编码突破资源预算 | 优先4090 NVENC；记录RAM/VRAM；不复制模型 | 已闭环 |
| 浏览器无WebCodecs | 启动前 `isConfigSupported` fail closed；不虚假ready | 已闭环 |
| 断线后session泄漏 | WebSocket finally置quit、join并从SessionManager移除 | 已闭环 |
| loopback被网页滥用 | 监听、peer和Origin三重loopback约束 | 已闭环 |
| 改坏已批准G-UX | 解码服务先独立交付；展示层只允许同位置canvas替换背景 | 已闭环 |
| A2失败无退路 | 原WebRTC实体与启动参数保留；失败回到文档门 | 已闭环 |

语义审查：A2只替换视频承载，不改变“声音主时钟、同页降级恢复、25FPS、本机离线、单用户”的既有规格，和 PRD/目标架构无冲突。
