# B3 验收标准：打断、旧轮隔离与长稳态

**状态**：PASS（2026-09-26）  
**证据等级**：只有目标机、真实 Chrome、真实模型和真实授权数据可形成 `e2e_accepted`。
**执行入口**：[`../../acceptance-command-manifest.md`](../../acceptance-command-manifest.md) §2；所有出门 runner 已实现并以目标机真实模型执行。

| ID | 用户场景与操作 | 证据 | 硬门 |
|---|---|---|---|
| B3-AC01 | 角色长回答的早/中/晚段各插话10次 | `interrupt.csv`、录屏、音频设备时间戳 | 30/30 回 listening；静音 P95≤400ms |
| B3-AC02 | cancel 后注入旧 LLM/TTS/Avatar 输出 | 事件流、generation 统计、DB diff | 旧字幕/音频/帧/写入均为0 |
| B3-AC03 | 连续问新问题 | ASR/角色文本配对 | 新回答只对应新问题，无跨轮污染 |
| B3-AC04 | 重复 cancel、断连、慢组件和超时 | fault matrix、task/queue 快照 | 幂等；无未处理异常；每组件≤1000ms回收；超过即本轮失败并明确降级，不以降级豁免硬门 |
| B3-AC05 | 100轮真实/授权语音压力 | 每轮事件与结果 JSON | 成功率≥95%；无固定轮数上限 |
| B3-AC06 | 1小时混合会话，至少20轮和10次打断 | 每分钟 RAM/VRAM/task/queue/latency CSV | 无崩溃/OOM/持续swap-in；指标无单调增长 |
| B3-AC07 | 结束与重复启动会话 | 端口、PID、队列、临时文件扫描 | 结束回 idle；队列/active task/临时音频为0 |

## 实测结论

| ID | 实测 | 证据 | 判定 |
|---|---|---|---|
| B3-AC01 | Windows Chrome 153，早/中/晚各10次，30/30；静音 P95=1.7ms | `audit/v1/B3/AC01/` | PASS |
| B3-AC02/03 | cancel 后旧字幕/音频/帧/DB 增量均为0；新轮转录与回答匹配 | `audit/v1/B3/AC02-03/` | PASS |
| B3-AC04 | 重复 cancel、断连、900ms hook deadline 共3/3 | `audit/v1/B3/AC04/` | PASS |
| B3-AC05 | 100/100 真实语音轮成功，严格事件序，持续 live Avatar | `audit/v1/B3/AC05/` | PASS |
| B3-AC06 | 60分钟、721采样、20完整轮+10打断；RAM 斜率1.633MB/min；VRAM峰值11.218GB | `audit/v1/B3/AC06/` | PASS |
| B3-AC07 | 3/3 生命周期；task/queue/临时音频归零，四端口存活 | `audit/v1/B3/AC07/` | PASS |
| B2.5回归 | 真实 Chrome 三轮首响 P95=4347.646ms≤7000ms | `audit/v1/B3/regression-b25-final/` | PASS |
| B2回归 | 真杀 Avatar 后604ms静态降级；同页恢复25 FPS并完成新一轮 | `audit/v1/B3/regression-b2-recovery/` | PASS |

## 测量口径

- 打断起点：服务端确认 `barge_in.detected` 的单调时钟。
- 终点：Chrome 音频设备不再输出旧 generation 的非静音样本。
- 样本按早/中/晚分桶并保存原始30行；不得删除失败样本后重算。
- 资源同时采集 Windows 项目 private bytes、WSL 项目 RSS、两侧可用内存、swap-in、NVML 和原始 `nvidia-smi`。
- 资源采样命令、验收工具单列和“无持续增长”斜率阈值统一使用命令清单 §5。

## 出门判定

全部 B3-AC、269项后端回归、3项 Avatar worker 回归、前端构建、B2.5 首响及 B2 Avatar 恢复均通过；开放 P0/P1=0。签署 AC-03、AC-05、AC-14 稳态部分和 OX-06，允许进入 B4 阶段门。
