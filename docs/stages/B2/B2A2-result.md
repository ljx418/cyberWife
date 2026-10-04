# B2-A2 实施与验收报告

**日期**：2026-09-25  
**结论**：PASS；A2-AC01～08全部通过，开放P0/P1=0，B2 OX-09签署

## 1. 交付实体

- Avatar新增`ws_h264`输出：NVENC优先、Annex-B access unit、每客户端2帧有界队列、慢消费者丢旧帧。
- 新增`/ws/v1/avatar`：限制loopback peer/Origin，原子创建、清理渲染会话。
- 前端`AvatarSession`改为WebSocket + WebCodecs + canvas；首帧才ready，断线静态降级并同页重连。
- Gateway PCM仍是唯一浏览器音频和主时钟；Avatar故障不反压语音。
- Launcher显式使用`--transport ws_h264`，原WebRTC代码保留为代码级回退。

## 2. 真实 Chrome 结果

| 门 | 实测 | 判定 |
|---|---|---|
| 首帧/解码 | Chrome 153；首帧535ms；512×768；NVENC | PASS |
| 连续画面 | 媒体节奏25fps；浏览器墙钟诊断约24.5fps；decoder backlog=0；传输丢帧=0；服务端finalfps 25.023～25.070 | PASS |
| 三周期故障 | 用户可见静态降级522/540/537ms | PASS |
| 音频不中断 | Avatar终止后非静音音频分片198/376/272；文本均完成 | PASS |
| 原页恢复 | 三轮均产生新session/连接代次，恢复后再次完成文本+音频；reload=0 | PASS |
| 推理能力 | 恢复轮inferfps 152.735～156.576 | PASS |
| 资源 | 项目13.157GiB；宿主可用2.303GiB；WSL可用约9.07GiB；GPU 9188/24564MiB；10秒swap增量0 | PASS（宿主余量接近门槛） |
| 隐私/监听 | 4173/7860/8010/8090/8091全部只监听loopback | PASS |
| 回归 | 后端263 passed/4 skipped；Avatar 2 passed；前端production build；浏览器合同 | PASS |

原始证据：

- `audit/v1/B2/avatar-recovery/h264-webcodecs-final.json`
- `audit/v1/B2/avatar-recovery/h264-recovery-final/result.json`
- `audit/v1/B2/avatar-recovery/resource-audit.json`

墙钟诊断值低于25的原因是WebCodecs保持约固定2帧解码缓冲；媒体时间戳连续为40ms、队列积压为0、传输丢帧为0，服务端实际输出≥25fps。该判定没有用媒体时间戳掩盖积压：出门条件同时要求backlog≤3、队列丢帧=0和服务端finalfps≥25。B5仍须用长稳态重新验证墙钟节奏是否发生累计漂移。

## 3. PRD检视与已知风险

- FR-10：正常口型、故障静态降级、音频继续、原页恢复均有真实产品浏览器证据。
- NFR资源/隐私：全部过门；宿主仅余约0.3GiB安全裕量，B3/B4禁止新增常驻大模型或无界缓存。
- 本阶段没有签署B3的打断≤400ms、100轮或1小时稳态；这些仍是下一阶段与B5责任。
- Gateway内部`media.state`事件在2.451～4.441秒到达，但前端由视频连接在约0.54秒完成用户可见降级；内部事件不得重新成为前端降级的唯一触发器。

