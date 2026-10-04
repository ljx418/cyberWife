# B2R Avatar 故障降级与原页恢复开发计划

**日期**：2026-09-25  
**前置门**：B0/B1/B2.5 PASS；ADR-009 已将 OX-09 归属 B2  
**目标**：真实 Avatar 进程故障时，声音和文本继续；页面在不刷新、不重建会话数据的情况下自动恢复视频连接，下一轮重新由口型驱动。

## 1. 当前事实与缺口

- LiveTalking/Wav2Lip 的真实 WebRTC、PCM 注入和双 FPS 已有一次通过证据：服务端 inferfps=114.72、客户端 finalfps=25.006。
- `MediaPipeline` 在 Avatar `open/push_audio` 失败时会发送 `media.state=static_fallback`，且先向浏览器发送 PCM，因此设计上不应反压声音。
- `RuntimeLauncher recover` 能按 PID 所有权恢复失败组件。
- 当前浏览器 `MediaSession` 只负责 PCM 播放，没有可复用的 Avatar WebRTC 连接与同页自动重连实体；仅用独立测试代码临时建立 RTCPeerConnection 会构成虚假产品验收。

## 2. 允许修改范围

1. 新增 `prototype/src/services/AvatarSession.ts`：只连接 loopback Avatar；管理 WebRTC video track、健康探测、静态降级回调和有界重连。
2. 扩展 `MediaSession.start/stop`：启动/释放 AvatarSession，但 Avatar 失败不得让音频启动失败；不得播放 Avatar 返回的重复音轨。
3. 必要时最小修改 `MediaPipeline` / `LiveTalkingAdapter` 的恢复状态事件，不改变 `AvatarPort` 业务语义。
4. 新增 `tests/b2/` 实际 Edge 故障恢复脚本和仅终止 launcher-owned Avatar 的安全测试脚本。
5. 不重构已批准视觉、不新增路由、不实现 B3 打断、不触碰记忆。

## 3. 实施顺序

1. 先补浏览器合同测试：loopback 限制、Avatar 不可用不阻塞 PCM、停止后无重连、同页自动重连、旧 PeerConnection 被关闭。
2. 实现最小 `AvatarSession` 并通过前端构建与合同测试。
3. 启动默认真实栈，以实际 Edge 页面建立 WebRTC；记录 inferfps/finalfps。
4. 在角色真实音频输出期间，校验 PID 记录与命令行 marker 后只终止 Avatar 进程；记录终止到 `static_fallback` 的时间、终止前后 PCM 序号/哈希及文本完成事件。
5. 调用 launcher `recover`，保持同一 Edge 页面不刷新；等待产品 `AvatarSession` 自动重连，在下一轮真实音频中再次记录双 FPS。
6. 连续执行 3 个“终止→降级→恢复→下一轮”周期，随后跑后端全量回归、前端 build、PRD 规格检视并归档原始 JSON/日志。

## 4. 安全与回滚

- 测试只能终止 `%LOCALAPPDATA%\cyberWife\pid\avatar.json` 记录且命令行含 `app.py --bind 127.0.0.1` 的 PID；不按端口杀进程。
- Avatar 地址必须是 `127.0.0.1/localhost/::1`；禁止公共 STUN、外部信令或模型下载。
- 重连并发固定为 1，退避有上限；`stop()` 后定时器、PeerConnection、MediaStreamTrack 全释放。
- 任一轮音频中断、文本缺失、降级>2秒、恢复需刷新、双FPS<25、资源越门或出现非loopback即 FAIL，回到计划审查。

## 5. 出门后体验

Avatar 正常时人物口型≥25FPS；Avatar 崩溃后页面在2秒内保留静态肖像提示，角色声音与字幕不中断；launcher恢复服务后，用户无需刷新，下一轮口型自动恢复。B2通过后才进入B3打断开发。

