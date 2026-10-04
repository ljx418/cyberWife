# B2R Windows Edge ↔ WSL2 Avatar 传输阻断审计

**日期**：2026-09-25  
**历史结论**：P1 BLOCKED；2026-09-25用户批准A2后已由`B2A2-result.md`关闭

## 1. 真实发现

目标机真实栈和 Edge 验证得到以下结果：

1. Avatar HTTP `/health`、`/offer` 可经 `127.0.0.1:8010` 正常访问；Wav2Lip CUDA 加载、warmup正常。
2. Windows Edge 默认 SDP 只给出随机 `*.local` host candidate；WSL2 的 `getent/resolvectl` 与原始 mDNS 查询均无法解析。
3. 禁用 Edge `WebRtcHideLocalIpsWithMdns` 后，candidate 为 `192.168.3.123`；Windows 与 mirrored WSL2 恰好共享该 IPv4，aiortc ICE 仍停在 `checking` 后失败。
4. 将浏览器候选仅在本机信令内改写为 `127.0.0.1` 或 `10.255.255.254`，ICE 同样无法建立。
5. 既有 WSL 内 aiortc 真实测试达到浏览器等价 finalfps=25.006；说明模型和渲染链可用，但不能证明 Windows 产品浏览器链。
6. 当时失败实验未签署B2；会导致重复WebRTC会话的`MediaSession`接线已撤回。该实验路径没有作为产品验收依据。
7. 当时收口回归为浏览器生命周期合同PASS、前端生产构建PASS、后端265 passed/4 skipped；最终A2回归为263 passed/4 skipped，二者测试收集范围不同。

根因是 Windows Edge 与 mirrored WSL2 间的 WebRTC UDP/ICE 跨命名空间不可达，不是 RAM/VRAM、TTS 或 Avatar 推理不足。

## 2. 可选路线

| 路线 | 实施 | 优点 | 代价/风险 | 结论 |
|---|---|---|---|---|
| A2：loopback WebSocket H.264视频 | Avatar以NVENC输出Annex-B；浏览器WebCodecs解码；音频仍走Gateway PCM主时钟 | 不改WSL全局网络；无公网/STUN；带宽和CPU优于JPEG | Chrome需支持WebCodecs；必须真实证明finalfps≥25 | **已批准并PASS** |
| B：WSL切回NAT以保留WebRTC | 修改用户级`.wslconfig`、`wsl --shutdown`，用Windows/WSL不同地址建立ICE | 保留既有WebRTC代码和编码效率 | 影响整机其他WSL项目；localhost、模型路径与生命周期需全回归；用户机器配置债务高 | 不推荐V1 |
| C：Avatar迁至Windows原生Python | 在Windows重建PyTorch/CUDA/aiortc与模型运行环境 | Windows Edge与Avatar同网络栈 | 环境重复、迁移成本和显存/内存回归风险最高 | 不推荐V1 |
| D：本地TURN/UDP relay | 新增Windows侧TURN或UDP代理 | 可保留WebRTC语义 | 新守护进程、端口和安全面；部署/恢复复杂，可能违反仅loopback边界 | 拒绝，除非A失败 |

## 3. 已实施路线 A2 的约束

- 只传视频帧；声音仍由既有 Gateway PCM 播放，避免双声与唇音时钟分叉。
- 单客户端、队列最多2帧；消费者慢时丢旧帧，不反压推理和音频。
- 仅 `ws://127.0.0.1:8010`；无外部监听、STUN或下载。
- 浏览器页不刷新；断线≤2秒静态降级，服务恢复后自动重连。
- 三周期真实故障恢复、inferfps/finalfps≥25、项目RAM≤14GB、VRAM≤22GB；不达门即停止，不降低门槛。
- NVENC不可用时仅允许同进程`libx264/ultrafast/zerolatency`回退；若FPS或资源失败，回到文档审查，不自动改用JPEG/MSE掩盖失败。

## 4. 决策请求

用户已批准A2；最终实现与证据见`B2A2-plan.md`、`B2A2-result.md`和`B2R-chrome-revalidation-result.md`。
