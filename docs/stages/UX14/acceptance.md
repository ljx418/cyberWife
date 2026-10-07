# UX14 验收标准：同场景单人物实时口型

| ID | 操作 | 证据 | 门槛 |
|---|---|---|---|
| UX14-AC01 | 安装批准序列 | job、active API、manifest | 三者`speaking_avatar_id`一致；`presentation=complete_scene` |
| UX14-AC02 | 播放Idle后进入live，并注入旧portrait/stale ID负例 | Headless Chrome DOM/CSS | 合法complete-scene首帧后Idle opacity=0、Canvas opacity=1；portrait或ID不一致时Idle保持可见、Canvas visibility=hidden且opacity=0；同屏人物数=1 |
| UX14-AC03 | 真实CosyVoice驱动 | PCM/H.264时间线、视频分析 | 768×432；final/infer FPS≥25；运动比>1.10；黑帧/冻结/丢帧=0 |
| UX14-AC04 | 正常停止或Avatar异常 | 浏览器状态 | 回到同一Idle/静态兜底，无第二人物、无纯黑 |
| UX14-AC05 | 用户三轮观看 | 人工评分 | 始终只有一个人物；背景/机位连续；口型同步和嘴部自然度均≥4/5 |

UX14-AC01～04可由机器签署；UX14-AC05必须由用户本人签署。
