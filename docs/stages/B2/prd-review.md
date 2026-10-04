# B2 PRD 规格检视

**日期**：2026-09-25  
**结论**：PASS；B2已出门并签署OX-09，可进入B3。B3/B4/B5尚未因此自动完成。

| PRD规格 | 真实结果 | 判定 |
|---|---|---|
| NFR-01 普通链首响P95≤7秒 | B2.5真实Chrome 30条P50/P95=5.567/6.392秒；用户授权盲听5/5 | PASS |
| FR-05 授权声音克隆 | CosyVoice2正确逐字稿30条CER=0.71%；Qwen保留显式回退 | PASS |
| FR-10 数字人口型≥25FPS | Chrome WebCodecs媒体节奏25fps，服务端25.023～25.070fps，零队列丢帧/积压 | PASS |
| Avatar故障不阻断音频 | 三轮用户可见降级522/540/537ms，故障后音频与文字继续 | PASS |
| Avatar原页恢复 | 三轮新session/decoder代次，恢复后再次对话，reload=0 | PASS |
| 资源预算 | 13.157GiB RAM、9188MiB VRAM、宿主/WSL可用均≥2GiB、10秒无swap活动 | PASS（宿主余量接近门槛） |
| 隐私边界 | 服务仅监听loopback；视频无STUN/TURN；原始PCM不落盘 | PASS |
| 回归 | 后端263 passed/4 skipped；Avatar 2 passed；前端build与浏览器合同PASS | PASS |

真实证据和保留风险见`B2A2-result.md`。B3必须独立完成30次真实打断、旧轮零泄漏、100轮压力及1小时稳态，不得以B2的Avatar故障恢复代替。
