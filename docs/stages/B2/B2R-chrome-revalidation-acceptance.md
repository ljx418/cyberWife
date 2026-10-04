# B2R Chrome 原路线复验验收标准

**日期**：2026-09-25  
**关联计划**：`B2R-chrome-revalidation-plan.md`

| 编号 | 用户场景 | 操作与真实证据 | 通过门槛 |
|---|---|---|---|
| CR-01 | 用户用 Windows Chrome 打开本地前端 | 独立 Chrome profile 访问本地 Vite，向真实 Avatar `/offer` 协商 | HTTP 成功且记录真实 Chrome 版本 |
| CR-02 | 数字人建立媒体连接 | 记录 ICE gathering、ICE connection、peer connection 状态 | 15秒内到 `connected/completed`，不得仅以 offer 200 判定 |
| CR-03 | 用户看到真实数字人画面 | 绑定远端 video track，统计 `requestVideoFrameCallback` | 5秒窗口至少收到1帧；若判定保留原路线，client finalfps≥25 |
| CR-04 | mDNS变量隔离 | 默认 Chrome 与测试专用禁用 mDNS Chrome 各执行一次 | 两组均有独立结果，候选只保留类别与数量 |
| CR-05 | 不污染机器 | 仅终止本轮 PID/独立 profile；不改全局防火墙和 `.wslconfig` | 无普通 Chrome、其他 WSL 项目或外部端口受影响 |
| CR-06 | 技术路线可决策 | 官方资料与实测联合评估 WebRTC、WebSocket/WebCodecs、MSE、WebTransport、桌面壳 | 给出唯一 V1 推荐路线及回退条件 |

### 规格检视

- FR-10 的最终签署仍要求 Windows 产品浏览器真实视频、Avatar 故障≤2秒静态降级、原页自动恢复、音频不中断。
- 本复验只决定传输路线，不签署 OX-09，也不降低 B2/B5 门槛。
- 若需要管理员级 Hyper-V 防火墙变更或 `wsl --shutdown`，归类为高风险机器配置路线，本轮不得自动执行。
