# RES1 验收标准

| ID | 场景/操作 | 出门门槛 |
|---|---|---|
| RES1-AC01 | 空闲基线与进程归因 | Windows、WSL、GPU数据同一时间窗；项目PID可追溯 |
| RES1-AC02 | 六组件真实probe | 全部ready且无模型替换/静默fallback |
| RES1-AC03 | 组合运行资源 | 项目RAM≤14GiB、VRAM≤22GiB、Windows与WSL最小余量各≥2GiB |
| RES1-AC04 | 60分钟真实组合复验 | 20完整+10打断成功，队列/任务无增长，AC03全程成立 |
| RES1-AC05 | 生命周期 | stop×2幂等、项目端口/PID归零；不误杀非项目进程 |

只有AC01～AC05全部通过才可把B5资源阻断改为绿；短测不通过时禁止用历史PASS覆盖。
