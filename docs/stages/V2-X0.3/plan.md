# V2-X0.3 输出音频控制计划

**目标**：增加音量、静音、当前回答重播、轻量动态压缩和支持时的输出设备选择，不持久化回答音频、不破坏A/V时钟。

## 实现顺序

1. `MediaSession`输出图改为`source→gain→compressor→meter→destination`，默认听感与V1等价。
2. 只在内存保留当前回答PCM，设置有界上限；新turn、打断、结束会话/页面立即清除。
3. 重播使用独立source集合，不发送首响确认、不驱动Avatar、不写盘。
4. `AudioContext.setSinkId`存在时允许选择；不存在时UI明确不支持。
5. 加入feature flag、主舞台轻量控制和自动化测试。

## 回滚

关闭`v2x.output_controls`隐藏UI；gain=1、mute=false、compressor bypass，MediaSession继续V1调度。
