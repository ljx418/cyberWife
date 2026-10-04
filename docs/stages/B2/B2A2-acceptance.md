# B2-A2 验收标准

**日期**：2026-09-25

| 编号 | 用户场景 | 真实操作与证据 | 出门门槛 |
|---|---|---|---|
| A2-AC01 | Chrome 打开数字人 | Windows Chrome连接loopback WebSocket，WebCodecs解码NVENC Annex-B | 支持探针PASS；5秒内首帧；无WebRTC连接 |
| A2-AC02 | 连续观看人物 | 同时统计H.264媒体时间戳、浏览器墙钟诊断、decoder backlog、WS丢帧与服务端metrics | 媒体节奏与服务端finalfps≥25，inferfps≥25，队列≤2、backlog≤3、传输丢帧=0；墙钟值如实报告且B5检查长期漂移 |
| A2-AC03 | 正常听角色说话 | 真实Gateway PCM送入同一Avatar session | 只有Gateway音频；非静音PCM持续；口型帧持续 |
| A2-AC04 | 说话中终止Avatar | 所有权校验后终止项目Avatar | ≤2秒进入`static_fallback`；文本和音频不中断 |
| A2-AC05 | 不刷新恢复 | launcher recover，等待同页自动重连 | reload=0；新session/decoder代次；下一轮恢复画面 |
| A2-AC06 | 重复稳定性 | 连续三次故障/恢复 | 3/3通过，无挂死、无孤儿session、无无界队列 |
| A2-AC07 | 资源与隐私 | 真实进程RAM/VRAM、逐秒swap、Windows与WSL监听审计 | 项目RAM≤14GiB、VRAM≤22GiB、双侧可用≥2GiB；连续3秒或>1MiB/10秒视为持续swap；仅loopback，无公网STUN/TURN |
| A2-AC08 | 回归 | 后端全量测试、前端build、协议合同 | 无新增失败；已批准G-UX布局、路由和主操作无回退 |

仅 A2-AC01～08 全部 PASS 且开放 P0/P1=0 时签署 B2 OX-09。首响放宽≤7秒与本阶段视频传输门槛无关。
