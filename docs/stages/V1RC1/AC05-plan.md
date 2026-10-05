# V1RC1-AC05 开发与验收计划：60分钟发布生命周期

## 目标与固定入口

使用 `ops/acceptance/Invoke-V1ReleaseAcceptance.ps1` 在当前候选上完整运行60分钟，20次完整对话+10次打断；不得缩短时长或复用UX7前证据。

## 步骤

1. `start`两次并比对受管PID，执行真实functional status。
2. Windows与WSL可用内存连续三次≥3GiB才进入正式采样。
3. 每5秒采集项目RAM、VRAM、两侧可用内存、swap、task、线程、队列与首响P95；30个真实动作均匀分布在60分钟。
4. 后30分钟以5分钟中位数计算Theil–Sen趋势。
5. 强制恢复Avatar，确认其他组件PID不变；连续`stop`两次，检查端口/PID记录归零。

## 硬门

- 完整20/20、打断10/10；无崩溃/OOM/采样错误。
- 项目RAM≤14GiB、VRAM≤22GiB、Windows/WSL最低可用均≥2GiB。
- RAM斜率≤20MiB/min；task/queue/thread≤0.1/min；延迟P95斜率≤20ms/min；连续重大swap分钟<3。
- Avatar恢复成功；重复start/stop幂等；最终受管端口和PID记录为0。
