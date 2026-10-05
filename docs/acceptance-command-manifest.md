# B3—B5 验收命令与证据清单

**版本**：1.2　**日期**：2026-10-06　**状态**：IMPLEMENTED / AUDITED
本清单定义已经实现的稳定命令接口。目标机证据已生成；诊断失败目录与最终通过目录必须并存，报告只能引用明确标记为正式候选的结果，禁止挑选性忽略失败历史。

## 1. 统一调用合同

```text
python -m tests.<stage>.<runner> --config config/runtime.local.toml \
  --evidence audit/v1/<STAGE>/<AC-ID> --build-id <id>
```

- `0`：场景全部通过；`2`：硬门失败；`3`：环境/模型不完整；`4`：证据不可用。除 0 外均不得签 PASS。
- 每个目录至少含 `manifest.json`、原始 JSON/CSV、JUnit XML、脱敏日志、环境/模型/配置哈希；浏览器场景另含截图或录像。
- runner 必须先校验是真实模型、真实目标机和 Windows Chrome；mock/fixture 只允许标记 `contract_passed`。
- 所有时间差使用同一进程的 monotonic ns；跨进程同时保留 wall-clock ISO-8601 与 clock-correlation 样本。

快速全量回归不得把`backend/tests`和根目录`tests`放进同一个pytest进程（两者包名同为`tests`，会发生导入遮蔽）。当前可重复命令为：

```text
PYTHONPATH=backend python -m pytest -q backend/tests
PYTHONPATH=.:backend python -m pytest -q tests/b3/test_accept_soak.py tests/b5/test_release_freeze.py
(cd workers/avatar && PYTHONPATH=. <avatar-python> -m pytest -q tests)
(cd prototype && npm run build && npm run test:e2e)
(cd prototype && npm run test:acceptance-core)
```

该限制属于验收工具P2：后续应提供统一根入口，避免执行者误把收集失败当成产品失败。

## 2. B3 命令

| ID | 未来命令入口 | 必须产物 |
|---|---|---|
| B3-AC01 | `python -m tests.b3.accept_interrupt --samples 30 --buckets early,mid,late` | `interrupt.csv`、浏览器音频时间戳、录像 |
| B3-AC02/03 | `python -m tests.b3.accept_generation_fence --inject-late all` | `events.jsonl`、`generation-counts.json`、`db-diff.json` |
| B3-AC04 | `python -m tests.b3.accept_cancel_faults --matrix all` | `fault-matrix.json`、task/queue 前后快照 |
| B3-AC05 | `python -m tests.b3.accept_turns --turns 100 --real-models` | 100行轮次结果与配对转录 |
| B3-AC06 | `python -m tests.b3.accept_soak --minutes 60 --min-turns 20 --interrupts 10` | 每分钟资源/延迟/queue CSV 与趋势判定 |
| B3-AC07 | `python -m tests.b3.accept_lifecycle --cycles 3` | PID/端口/queue/temp 扫描 |

## 3. B4 命令

| ID | 未来命令入口 | 必须产物 |
|---|---|---|
| B4-AC01/02 | `python -m tests.b4.accept_memory_recall --real-session-id <B3-id>` | candidate/FTS/vector/fusion 排名与 token 预算 |
| B4-AC03/04 | `python -m tests.b4.accept_edit_delete --real-session-id <B3-id>` | 四层查询与 DB diff |
| B4-AC05 | `python -m tests.b4.accept_purge --fault-each-write` | transaction/audit/integrity 报告 |
| B4-AC06/07 | `python -m tests.b4.accept_no_record --mode create,mid-session --capture-loopback` | 表计数、WAL、audit、网络与文件痕迹扫描 |
| B4-AC08 | `RETENTION_NOW=<iso> python -m tests.b4.accept_retention --days 29,30,31` | 行级 before/after 与重试事件 |
| B4-AC09 | `python -m tests.b4.accept_fail_closed --cases no-vector,wrong-dim,low-disk` | health/error、文件和数据库完整性 |

## 4. B5 完整性门与总回归命令

| ID | 未来命令入口 | 必须产物 |
|---|---|---|
| B5-AC00 | `python -m tests.b5.accept_completeness` | 授权、资产版本、人设、默认入口、6设置API、HostBridge 合同矩阵 |
| AC-01/02/11 | `python -m tests.b5.accept_setup_assets_profile` | API/浏览器/JUnit/重启一致性 |
| AC-03～10/14 | `python -m tests.b5.accept_conversation_suite --real-models` | AC逐项 manifest 与组合资源曲线 |
| AC-04A | `python -m tests.b25.accept_warm_cache --positive-rounds 3 --negative-min 24` | 命中/负例/失效/内存 CSV |
| AC-12 | `python -m tests.b5.accept_recovery --components all --cycles 3` | functional probe、恢复时延、页面连续性录像 |
| AC-13 | `python3 tests/b5/accept_egress_whitebox.py && python3 tests/b5/accept_privacy.py --real-models` | 默认运行面白盒、真实五轮、项目进程连接、日志/Git/音频扫描；不执行会中断宿主终端的物理断网 |
| OX-01～12 | `python -m tests.b5.accept_optimization_regression --all` | OX 总矩阵 |
| 发布生命周期 | `powershell.exe -File ops/acceptance/Invoke-V1ReleaseAcceptance.ps1 -Minutes 60` | start×2/status/recover/stop×2、备份恢复卸载清除报告 |

## 5. 系统资源采样合同

- Windows：`Get-Counter '\Memory\Available MBytes','\Process(*)\Private Bytes','\Process(*)\Working Set'`，每5秒；按 PID allowlist 归因。
- WSL：每5秒读取 `/proc/meminfo` 的 `MemAvailable`、项目 PID 的 `/proc/<pid>/status` `VmRSS` 与 `/proc/vmstat` 的 `pswpin`。
- GPU：NVML 按 PID + CUDA free delta + 原始 `nvidia-smi` 同时保存；差异>1GB 判失败并调查。
- “无持续增长”：最后30分钟对5分钟中位数序列做 Theil–Sen 斜率；RAM>20MiB/min、项目OS线程或应用task>0.1/min、queue>0.1/min 或延迟P95>20ms/min 均失败；同时任何硬上限越界立即失败。
- “无持续 swap-in”：`pswpin` 是宿主级4KiB页计数，采样器自身会产生零星换入；以连续3个一分钟桶均≥256页（即每分钟≥1MiB）定义为持续换入并判失败，同时保留总页数和分钟峰值。不得用单页变化冒充内存压力，也不得忽略达到该阈值的真实换入。
- 验收工具自身按 PID 单独记录，不计入项目 14GB，但宿主/WSL 可用≥2GB 的系统硬门包含其影响。

## 6. V1FINAL现场门

在四组件健康、用户已知悉Chrome/Narrator将抢占焦点时，从Windows PowerShell执行：

```powershell
.\ops\acceptance\Invoke-ACC1HumanGate.ps1 -AcceptFocusChange -Operator "验收人姓名"
```

缺少`-AcceptFocusChange`必须在启动任何窗口前失败。取证器使用安装版headed Chrome和默认物理输入，自动验证PCM帧、至少三轮完整事件链、一次打断、取消后接续、当前active avatar和停止后Idle推进；人工只签Narrator五任务及三项自然度评分。`audit/v1/ACC1/human-gate.json`不得包含音频、字幕或回答正文，只有总结果为`PASS`且退出码为0才能关闭ACC1/UX6现场门。

## 7. INST1-AC06独立干净环境门

开发机先运行只读`fingerprint`；新Windows用户+干净默认WSL以开发机两个哈希作为拒绝值，再执行正式`accept`：

```powershell
.\ops\acceptance\Invoke-INST1CleanMachineAcceptance.ps1 -Action fingerprint
.\ops\acceptance\Invoke-INST1CleanMachineAcceptance.ps1 `
  -Action accept -AcceptCleanEnvironment `
  -RejectWindowsSidHash "<开发机hash>" -RejectWslMachineIdHash "<开发机hash>" `
  -WheelhouseWsl "/path/to/wheelhouse" `
  -ArtifactManifestWsl "/path/to/local-artifacts.private.json"
```

身份任一相同、数据根/venv/config/本机注册表任一预存在、Git跟踪文件不干净、离线清单/本地制品清单或源码revision不可用时均在安装/启动前失败。正式报告必须绑定workspace revision、wheelhouse manifest SHA256、本地制品清单SHA256和CosyVoice revision，并通过start×2/status/recover/stop×2；当前机负例不能关闭AC06。

## 8. 实现前检查

进入每个子阶段前，负责 Agent 必须先创建本阶段 runner 的合同测试与证据 schema，再实现产品功能。若实际环境无法提供本清单中的采样源，只能返回计划阶段修订，不能删减证据项或降低硬门。
