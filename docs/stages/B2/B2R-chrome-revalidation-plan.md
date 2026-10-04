# B2R Chrome 原路线复验与传输选型计划

**日期**：2026-09-25  
**阶段性质**：A2 实施前技术复验门；不改变 PRD 体验承诺  
**用户决策**：已批准 A2，但要求先在 Windows Google Chrome 下复验原 WebRTC 路线并联网调查更优方案

## 1. 目标与边界

目标是在不修改用户全局网络配置、不降低 B2 验收门槛的前提下，回答三个问题：

1. Chrome 153 是否能直接完成 Windows 浏览器到 mirrored WSL2 Avatar 的 WebRTC/ICE 连接；
2. Edge 失败是否属于浏览器差异，还是 WSL2 UDP/ICE 网络边界问题；
3. A2（loopback WebSocket + H.264/WebCodecs）是否仍是 V1 最小冲击路线。

本轮只允许启动项目自有服务、Vite 与隔离测试 Chrome；不修改 `.wslconfig`、Hyper-V 防火墙、系统代理或普通 Chrome 配置。

## 2. 真实环境与测试矩阵

- 浏览器：`C:\Program Files\Google\Chrome\Application\chrome.exe`，独立临时 profile、独立 CDP 端口。
- 后端：WSL2 Ubuntu 24.04，`networkingMode=mirrored`，Avatar 仅监听 `127.0.0.1:8010`。
- 场景 C1：Chrome 默认配置，验证候选类型、ICE/peer 状态及收到的视频帧。
- 场景 C2：仅为隔离测试 Chrome 禁用 `WebRtcHideLocalIpsWithMdns`，重复同一验证。
- 对照：既有 Edge 证据、WSL 内 aiortc 真实 finalfps=25.006。

## 3. 执行顺序

1. 只读记录 Chrome、WSL 网络模式和 Hyper-V 防火墙状态。
2. 启动项目 Avatar 服务与 Vite；探针使用与产品相同的 `/offer` SDP/ICE 协议。
3. 依次执行 C1、C2，每组最长等待 15 秒，不做候选改写、不使用 STUN/TURN。
4. 记录浏览器版本、候选类别、ICE/connection 状态时间线、视频首帧和帧率；原始局域网地址不写入审计产物。
5. 对照微软、Chromium、W3C 官方资料完成方案矩阵和架构建议。

## 4. 决策规则

- **保留 WebRTC**：Chrome 默认配置能稳定连接并接收真实视频帧；随后执行 B2 三周期恢复验收。
- **条件保留 WebRTC**：仅修改项目可控启动参数即可稳定连接，且不要求管理员权限或全局网络变更。
- **进入 A2**：C1/C2 均失败，或修复依赖全局 Hyper-V 防火墙/WSL 重启；采用独立视频 WebSocket，音频仍以 Gateway PCM 为主时钟。
- **重新审查**：A2 所需 H.264 编码无法在 16GB 空闲内存、项目 RAM≤14GB、VRAM≤22GB 和 finalfps≥25 下运行。

## 5. 出门条件

- 两组 Chrome 结果均有机器生成 JSON 和可复核状态时间线；
- 明确区分浏览器、mDNS、Hyper-V 防火墙和 WSL 地址空间因素；
- 推荐路线包含实施成本、架构冲击、用户体验、回退方案与证据限制；
- 不以 mock、健康端点或 WSL 内客户端冒充 Windows Chrome 产品链路。
