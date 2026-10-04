# B5 验收标准：V1 发布候选

**状态**：PASS — B5.1～B5.6全部出门；最终矩阵见`B5.6-prd-review.md`。  
**执行入口**：[`../../acceptance-command-manifest.md`](../../acceptance-command-manifest.md) §4。B5.3按用户在2026-09-26澄清的安全口径执行：不关闭会中断宿主终端的公网网络，改用真实功能完备性、默认运行面的出站白盒审查、连续项目进程连接采样三重证据。

## 0. B5-AC00 完整性前置门（不可豁免）

在运行任何组合回归前，`python -m tests.b5.accept_completeness` 必须以真实后端返回 0，并证明：授权授予/撤销和素材阻断；人物/声音版本列表、预览、原子激活与上一版恢复；完整人设乐观并发和跨重启；根路由默认进入批准主舞台且开发参数可回退 legacy；设置抽屉六类 API 全为真实响应；HostBridge 安全空实现无越权。证据归档 `audit/v1/B5/B5-AC00/`。任一项缺失不得启动 §1。

## 1. 总验收

- 完整执行 `acceptance-plan.md` 的 AC-01～AC-14 和 AC-04A。
- 完整执行 B2.5 OX-01～12；普通、缓存、打断、Avatar恢复必须在同一发布候选构建上无回退。
- 所有场景保存构建ID、模型哈希、配置摘要、原始样本、截图/视频、脱敏日志、JUnit/JSON/CSV和缺陷ID。

## 2. 发布硬门

| 类别 | 出门门槛 |
|---|---|
| 体验 | 20轮成功率≥95%；普通首响P95≤7秒；打断P95≤400ms；Avatar infer/final FPS均≥25 |
| 稳定 | 1小时无崩溃/OOM/未处理异常，延迟、task、queue无持续增长 |
| 资源 | VRAM≤22GB；项目RAM≤14GB；宿主/WSL可用均≥2GB；无持续swap-in |
| 数据 | 删除后四层0召回；no-record业务持久化0；DB integrity PASS |
| 隐私 | 原始麦克风音频0落盘；默认可执行公网出站路径0；允许集合外 DNS/HTTP/TCP 已建立连接0；日志/Git无敏感正文和私有资产 |
| 运维 | start/stop/status/recover幂等；备份恢复一致；卸载与数据清除边界明确 |
| 可用性 | 1920/1366/420、键盘、读屏、reduced-motion均通过；真实后端错误不破坏已批准视觉 |

CosyVoice 只有在启动 functional probe 失败、单发布候选30条普通链P95>7秒、CER>5%或资源越门时由 `HealthAggregator` 一次性切到 Qwen 回退并保持 degraded；同一进程生命周期不自动切回，防止震荡。恢复 CosyVoice 必须由用户点击单项恢复并重新通过 probe。资源趋势判定使用命令清单 §5。

## 3. Go/No-Go

只有 AC 全部 PASS、开放 P0/P1=0、模型/许可证/配置/schema 已冻结且安装/备份/恢复/卸载/清除演练完成，才能标记 V1 Go。P2 只有用户书面接受且有明确绕行时可保留。
