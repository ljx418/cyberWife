# ADR-001：V1 采用 Windows + WSL2 原生运行拓扑

## 状态
Accepted — 2026-09-22

## 背景
目标机器已有 Windows、WSL2 和 24GB NVIDIA GPU；参考链路以 Windows llama.cpp 与 WSL 推理服务为主。Docker Desktop daemon 当前不可用，容器化不应阻塞 V1 体验验证。

## 备选方案
1. 全部 Windows 原生：路径直观，但 Python/CUDA 依赖冲突高。
2. Windows llama.cpp + WSL2 应用/语音/Avatar：贴合现有链路，跨边界可控。
3. Docker Desktop Compose：迁移更强，但增加 GPU、网络、卷和镜像调试面。

## 决策
V1 采用方案 2；所有端口、模型和数据路径外置。Docker Compose 归入 V2。

## 后果
V1 可先证明体验与性能；代价是必须实现可靠的 Windows/WSL 启动器和网络探测。V2 可替换宿主，不改变业务接口。

