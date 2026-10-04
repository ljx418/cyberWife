# ADR-010：Avatar采用loopback WebSocket H.264与WebCodecs

## 状态

Accepted — 2026-09-25；取代ADR-003/ADR-005中“Avatar使用本机WebRTC”的部分，不改变其余REST/WebSocket和离线边界。

## 背景

Windows Edge与Chrome 153访问mirrored WSL2内真实LiveTalking时，HTTP offer可用，但默认mDNS候选和关闭mDNS后的IPv4 host候选均停在ICE checking且无视频帧。保留WebRTC需要管理员级Hyper-V防火墙/WSL全局配置、WSL重启，或新增TURN/Windows原生运行时，超出V1可控部署边界。

## 决策

- Gateway WebSocket继续承载状态、文本、20ms PCM和控制；PCM是唯一浏览器音频与主时钟。
- AvatarRuntime通过`ws://127.0.0.1:8010/ws/v1/avatar`只发送Annex-B H.264 access unit；优先NVENC，失败可在同进程回退libx264。
- Windows Chrome以WebCodecs `VideoDecoder`解码并绘制canvas；每客户端队列最多2帧，慢消费者丢旧帧，不反压音频。
- peer、Origin和监听地址必须为loopback；不使用STUN/TURN或公网信令。
- Avatar断线由产品`AvatarSession`在2秒内切静态图并同页重连；ready必须等到首个真实解码帧。

## 后果

消除了WSL UDP/ICE机器配置依赖，保持模型、音频、业务端口和已批准UX不变；代价是V1浏览器需支持WebCodecs，且视频与音频同步由时间戳/有界丢帧而非WebRTC媒体栈保证。B2实测首帧535ms、三轮降级≤540ms、媒体/服务端25fps、零积压/丢帧；B5需复跑1小时漂移。

## 回退

原WebRTC实体保留为代码级回退，但不得在V1自动启用。若目标浏览器不支持H.264 WebCodecs，必须回到架构门评估MSE或桌面壳，不以修改全局防火墙作为静默安装步骤。

