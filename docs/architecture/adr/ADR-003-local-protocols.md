# ADR-003：REST + WebSocket + 本机 WebRTC

## 状态
Superseded in part — 2026-09-25；Avatar媒体部分由ADR-010取代

## 背景
设置和记忆是请求/响应；对话需要双向流和取消；Avatar 需要实时媒体。全部轮询会增加延迟，全部 WebRTC 会让业务接口复杂。

## 决策
REST承载配置、资产、记忆与健康；Gateway WebSocket承载状态、文本、音频chunk和控制事件。原LiveTalking WebRTC决策因Windows浏览器↔mirrored WSL2 ICE失败被ADR-010取代为H.264 WebSocket/WebCodecs。全部协议限制loopback。

## 后果
协议各司其职并可独立测试；需要统一 `session_id/turn_id/event_seq` 处理乱序和取消。
