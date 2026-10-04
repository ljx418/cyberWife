# B2R Windows Chrome 复验与传输选型结论

**日期**：2026-09-25  
**结论**：Chrome 原 WebRTC 路线 FAIL；A2（loopback WebSocket + H.264/WebCodecs）是 V1 最小冲击方案

## 1. 目标机实测

测试使用 Windows Google Chrome `153.0.8010.53`、隔离 profile、真实 Wav2Lip/aiortc `/offer`，未修改 `.wslconfig`、Hyper-V 防火墙或普通浏览器设置。

| 场景 | 候选 | 15秒结果 | 视频帧 | 原始证据 |
|---|---|---|---:|---|
| Chrome 默认 | host/UDP/mDNS | ICE `checking`，连接未完成 | 0 | `audit/v1/B2/avatar-recovery/chrome-default.json` |
| 仅测试进程禁用 `WebRtcHideLocalIpsWithMdns` | host/UDP/IPv4 | ICE `checking`，连接未完成 | 0 | `audit/v1/B2/avatar-recovery/chrome-no-mdns.json` |

两组均能完成 HTTP offer/session 创建，但均不能建立媒体连接。由此排除“只因 Edge 或 mDNS 导致失败”；结合 WSL mirrored 网络与 Hyper-V 默认入站阻断状态，判断为 Windows 浏览器与 WSL UDP/ICE 边界问题。此根因是基于实测与官方网络模型的工程推断，不宣称为微软已确认的单一缺陷。

## 2. 官方事实核查

- 微软说明 mirrored mode 支持宿主与 WSL 通过localhost互通，但入站连接仍受Hyper-V firewall管理；放行需要管理员级防火墙配置：<https://learn.microsoft.com/windows/wsl/networking>
- `hostAddressLoopback=true` 只适用于mirrored mode、默认关闭，修改WSL配置后需要重启WSL：<https://learn.microsoft.com/en-us/windows/wsl/wsl-config>
- Chromium 默认可用mDNS隐藏本地WebRTC IP，企业策略可按URL放开；本机关闭该变量仍失败：<https://chromium.googlesource.com/chromium/src/+/376fc41e87a058f7a7b300b0ec3a4982b4ec0960/components/policy/resources/templates/policy_definitions/Miscellaneous/WebRtcLocalIpsAllowedUrls.yaml>
- WebCodecs `VideoDecoder` 支持低延迟提示；H.264无`description`时按Annex-B，关键帧应携带参数集：<https://www.w3.org/TR/webcodecs/>、<https://www.w3.org/TR/webcodecs-avc-codec-registration/>
- loopback来源属于潜在可信来源，可使用需要secure context的WebCodecs：<https://www.w3.org/TR/secure-contexts/>

## 3. 路线比较

| 路线 | 开发/运维成本 | 架构冲击 | 体验影响 | V1结论 |
|---|---|---|---|---|
| A2：WebSocket H.264 + WebCodecs | 中；新增编码输出、WS路由、浏览器解码器 | 小；只替换视频承载，PCM主时钟与模型不变 | 低延迟、同页恢复；依赖Chrome WebCodecs | **已选且实测通过** |
| WebRTC + Hyper-V规则/`hostAddressLoopback` | 中开发、高机器运维；管理员权限和WSL重启 | 中；安装器必须修改全局网络状态 | 理论上延迟低，但机器差异和首次配置明显 | 不用于V1 |
| WSL切回NAT | 中到高；全服务地址和生命周期回归 | 大；影响其他WSL项目与localhost假设 | 无直接UI变化，部署脆弱 | 不推荐 |
| Windows原生Avatar后端 | 高；重建CUDA/Python/模型环境 | 大；双平台运行时与路径分叉 | 可保留WebRTC，启动与维护更重 | 不推荐 |
| 本地TURN/UDP relay | 高；新增守护进程、端口、安全配置 | 大 | 可能稳定ICE，但故障面扩大 | 拒绝V1 |
| MSE/fMP4 over WebSocket | 中高；新增封装、SourceBuffer管理 | 中 | 分段和buffer增加首帧/恢复延迟 | A2失败才考虑 |
| WebTransport | 高；HTTP/3/TLS/QUIC与证书 | 大，仍跨UDP边界 | 低延迟潜力，当前部署复杂 | 不适合V1；规范仍在演进：<https://www.w3.org/TR/webtransport/> |
| Electron/WebView2/Tauri桌面壳 | 高；打包、升级、签名、安全面 | 大；产品从浏览器转桌面应用 | 适合未来透明置顶桌宠，不改善当前WSL后端本质 | V2候选；Electron安全基线见 <https://www.electronjs.org/docs/latest/tutorial/security>，WebView2宿主安全见 <https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/security> |

## 4. 架构结论

V1保持Windows Chrome前端与WSL后端，通过`127.0.0.1` HTTP/WebSocket TCP交互；Gateway WebSocket继续承载事件和PCM，Avatar WebSocket只承载有界H.264视频。未来若产品必须成为透明、置顶、可穿透的真正桌宠，可在不改后端协议的前提下增加WebView2/Tauri/Electron壳，但不应在V1提前承担打包和安全债务。

