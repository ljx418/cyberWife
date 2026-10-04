# B2R Avatar 恢复验收标准

**日期**：2026-09-25  
**证据原则**：本文件记录原WebRTC验收口径；Chrome复验后该传输路线被否决。最终门槛与证据由`B2A2-acceptance.md`/`B2A2-result.md`接替，mock仍只验证合同。

| ID | 用户场景与操作 | 必须证据 | 硬门槛 |
|---|---|---|---|
| B2R-AC01 | 正常对话并观察人物 | Edge video帧时间、Avatar metrics | inferfps≥25且浏览器finalfps≥25 |
| B2R-AC02 | 角色说话时终止Avatar进程 | PID所有权记录、WS事件、PCM序号/哈希 | `static_fallback`≤2秒；终止后仍有非静音PCM；文本final完整 |
| B2R-AC03 | 不刷新页面执行launcher recover | 页面导航计数、PeerConnection代次、健康时间线 | 页面reload=0；单一重连；服务ready后自动建立新PeerConnection |
| B2R-AC04 | 恢复后的下一轮继续说话 | 第二轮PCM、video帧和metrics | 无需重建用户设置；下一轮infer/final FPS均≥25；不再报旧fallback |
| B2R-AC05 | 重复故障恢复 | 三轮原始JSON与日志 | 3/3满足AC01～04；无hang、无孤儿重连任务 |
| B2R-AC06 | 资源与隐私 | RAM/VRAM/swap、端口/出站、文件增量 | RAM≤14GB、VRAM≤22GB、双侧可用≥2GB、无持续swap-in；仅loopback；PCM不落盘 |
| B2R-AC07 | 回归 | 后端测试、前端测试/build | 无新增失败；已批准页面布局/路由/主操作不变 |

出门要求：B2R-AC01～07 全部 PASS、开放 P0/P1=0。B2 只签署 OX-09；OX-06 仍由 B3 签署，B5 重跑完整组合。
