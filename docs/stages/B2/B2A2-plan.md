# B2-A2 WebSocket H.264 / WebCodecs 开发计划

**日期**：2026-09-25  
**前置结论**：Windows Chrome 153 默认与禁用 mDNS 两组 WebRTC 均停在 ICE checking；用户已批准 A2  
**目标**：替换浏览器视频传输，不替换 Wav2Lip、Gateway PCM 音频、前端视觉设计或用户会话语义

## 1. 目标架构

```text
Gateway PCM（既有主时钟） ─HTTP 20ms PCM─> AvatarSession/Wav2Lip
                                              │ BGR帧
                                              ▼
                                      H264WebSocketOutput
                                     NVENC，失败回退libx264
                                              │ Annex-B access unit
                                              ▼
Windows Chrome ─ws://127.0.0.1:8010/ws/v1/avatar─> VideoDecoder ─> canvas
```

### 明确边界

- 视频与控制/音频分离，避免视频背压阻塞 Gateway PCM。
- WebSocket 每客户端最多积压2帧，慢消费者丢旧帧；音频不进入本通道。
- 服务只监听 loopback；WebSocket 校验 loopback Origin/peer。
- 编码优先 `h264_nvenc`，同进程回退 `libx264/ultrafast/zerolatency`，不增加常驻守护进程。
- 浏览器按 W3C Annex-B 规则将每个 access unit 交给 `VideoDecoder`，canvas 只保留最新帧。

## 2. 实施实体

| 实体 | 动作 | 职责 |
|---|---|---|
| `streamout/h264_websocket.py` | 新增 | 25FPS节拍、H.264编码、关键帧、2帧有界广播 |
| `server/routes.py` | 修改 | `/ws/v1/avatar` 原子创建/销毁渲染会话，限制loopback |
| `avatars/base_avatar.py` | 修改 | 注册 `ws_h264` 输出，不改变推理算法 |
| `config.py` / launcher | 修改 | 显式选择 `ws_h264`，保留 `webrtc` 回滚能力 |
| `prototype/src/services/AvatarSession.ts` | 修改 | WebSocket生命周期、WebCodecs解码、canvas绘制、同页退化/重连 |
| `tests/b2/*` | 新增/修改 | 协议合同、Windows Chrome真实帧、三周期恢复、资源门槛 |

## 3. 执行批次

1. A2-1：后端输出与协议合同；用真实 NVENC 编码帧验证 Annex-B、关键帧和队列上限。
2. A2-2：浏览器解码控制器；Chrome 真实 `VideoDecoder.isConfigSupported`、首帧与25FPS验证。
3. A2-3：Gateway PCM接入与三周期故障恢复，完成原页恢复、音频不中断及资源证据。
4. A2-4：全量回归、PRD检视、B2 OX-09签署或打回。

## 4. 回退

- 代码级回退：launcher 将 `--transport ws_h264` 改回 `webrtc`；原 `/offer` 与 aiortc 保留。
- 运行时回退：NVENC初始化失败时只回退 CPU x264，不切换模型/分辨率/FPS。
- 若 Chrome 不支持所发 codec 或真实 finalfps<25，停止在 B2，不以 JPEG/MJPEG 自动降级掩盖失败。
