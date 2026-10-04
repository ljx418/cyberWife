# ADR-005：离线优先且不依赖公共 STUN

## 状态
Accepted — 2026-09-22

## 背景
PRD 要求断网完整对话。参考方案的公共 Google STUN 会造成外联和离线不确定性。

## 决策
所有服务仅监听loopback；Avatar按ADR-010使用H.264 WebSocket，不配置公共STUN/TURN。禁用遥测和模型自动下载，运行时外联视为发布阻断。原WebRTC host-candidate约束只适用于保留的回退实现。

## 后果
隐私边界清晰且断网可用；V1 不支持其他设备访问。未来远程访问必须新增威胁模型和 ADR。
