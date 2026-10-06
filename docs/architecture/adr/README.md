# cyberWife 架构决策索引

| ADR | 决策 | 状态 |
|---|---|---|
| [ADR-001](ADR-001-v1-native-runtime.md) | V1 采用 Windows + WSL2 原生运行拓扑 | Accepted |
| [ADR-002](ADR-002-modular-core.md) | 模块化应用核心与外部推理进程 | Accepted |
| [ADR-003](ADR-003-local-protocols.md) | REST + WebSocket + 本机 WebRTC（Avatar部分被ADR-010取代） | Superseded in part |
| [ADR-004](ADR-004-local-memory-store.md) | SQLite + FTS5 + sqlite-vec 管理本地记忆 | Accepted |
| [ADR-005](ADR-005-offline-network-boundary.md) | 离线优先且不依赖公共 STUN | Accepted |
| [ADR-006](ADR-006-storage-placement.md) | 源码在 C 盘，运行数据在 WSL2 ext4 | Accepted |
| [ADR-007](ADR-007-docker-v2.md) | Docker 容器化作为 V2 目标 | Accepted |
| [ADR-008](ADR-008-cosyvoice-default-and-latency-gate.md) | V1默认TTS切换为非TensorRT CosyVoice并采用7秒首响门 | Accepted |
| [ADR-009](ADR-009-stage-gate-ownership.md) | B2.5验首响/缓存、B2验Avatar恢复、B3验打断、B5完整组合回归 | Accepted |
| [ADR-010](ADR-010-avatar-h264-websocket.md) | Avatar改为loopback WebSocket H.264 + WebCodecs | Accepted |
| [ADR-011](ADR-011-avatar-independent-liveness.md) | Avatar独立存活通道 + H.264 WS应用层心跳 | Accepted |
| [ADR-012](ADR-012-single-machine-portability-gate.md) | V1以单机隔离可移植性为最低部署门，独立干净机保留为增强项 | Accepted |

任何决策变更需新增或取代 ADR，同时更新 PRD、目标架构、追踪矩阵、验收计划和 Draw.io。
