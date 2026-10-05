# V1RC1-AC05 60分钟发布生命周期结果

**日期**：2026-10-06
**结论**：PASS

证据目录：`audit/v1/V1RC1/AC05-release60m-rerun/`

| 指标 | 实测 | 门槛 | 判定 |
|---|---:|---:|---|
| 完整轮 | 20/20 | 20 | PASS |
| 打断轮 | 10/10 | 10 | PASS |
| 资源样本 | 721（每5秒） | 无采样错误 | PASS |
| 项目RAM峰值 | 13,775.637MiB | ≤14,336MiB | PASS |
| 后30分钟RAM斜率 | 0.390333MiB/min | ≤20 | PASS |
| GPU显存峰值 | 11.219GiB | ≤22GiB | PASS |
| Windows最低可用 | 6,181.547MiB | ≥2,048MiB | PASS |
| WSL最低可用 | 8,989.289MiB | ≥2,048MiB | PASS |
| task/queue/thread斜率 | 全部0 | ≤0.1/min | PASS |
| 首响P95斜率 | -1.8342ms/min | ≤20ms/min | PASS |
| 连续重大swap分钟 | 0 | <3 | PASS |
| Avatar | 当前Crop V2、协议v2、89,981帧 | 当前人物+协议v2 | PASS |

生命周期：重复start未改变PID；Avatar强制恢复 `25428→27316`，其余组件PID不变；stop×2成功，最终受管端口0、PID记录0。失败的首次TypeError批次和两个1分钟smoke均保留，未计入正式通过。

## PRD 检视

FR-08、FR-09、FR-10、FR-15、FR-17与NFR-01～04在当前候选上无回退；整句一次CosyVoice、当前人物、打断和资源门同时成立。该结果不替代Narrator人工听感、完整物理麦克风脚本、干净Windows+WSL独立安装或UX6完整口型/Idle主观签署。
