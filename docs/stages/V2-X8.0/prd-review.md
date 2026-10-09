# V2-X8.0 PRD规格检视

| PRD承诺 | 本轮实现 | 结论 |
|---|---|---|
| 单一人物、完整场景、无第二图层 | 两候选使用同一250帧完整场景；浏览器协议和单Canvas合同未改 | ALIGNED |
| 实时口型和25fps | 两候选finalfps≥25，真实PCM驱动，黑帧/缺口/持续冻结0 | ALIGNED |
| 音频为唯一主时钟 | 继续使用原H.264 WS与浏览器音频时钟；未让Idle或动作视频接管 | ALIGNED |
| 16GB空闲内存/24GB VRAM | MuseTalk串行运行，组合观测未越界；明确禁止双常驻 | ALIGNED |
| 体验无回退 | 默认未切换；MuseTalk须人工四维评分均≥4/5且不低于基线 | FAIL-CLOSED |
| 其他形象 | 本轮只校准当前批准人物；X3.4/X3.5仍需独立证据 | DEFERRED AS PLANNED |
| 本机离线核心链 | 下载后canary以HF离线变量运行；语音、图像、音频均未上传 | ALIGNED |

未发现致命或重大规格偏移。MuseTalk不是“LiveAvatar效果自动开启”，而是LiveTalking内另一个生成插件；正式迁移需要显式engine合同、许可证关闭、人工门与其他形象回归。
