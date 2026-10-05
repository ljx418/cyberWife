# V1RC1-R3 验收与 PRD 检视

**状态**：PASS（2026-10-06）

## 真实验收

| 项目 | 结果 | 判定 |
|---|---:|---|
| Windows Chrome 154 普通链 | 30/30 complete、30/30 normal、缓存命中0 | PASS |
| ASR final→浏览器首个非静音 | P50=4272.305ms、P95=4878.109ms、最大=5328.328ms | PASS（≤7000ms） |
| TTS首包分段 | 1550.386–1967.455ms | PASS；跨轮窗口增长已消失 |
| 浏览器确认 | 每轮恰好1次，所有轮存在非静音块 | PASS |
| 资源 | WSL `MemAvailable`=7241MiB、Swap使用=0；VRAM=9.16/23.99GiB | PASS |
| 证据 | `audit/v1/V1RC1/R3-AC03-normal30/` | 已落盘 |

相对R2失败批次 P95=7727.328ms，R3下降36.9%；样本数量、语料、浏览器口径和硬门未放宽。

## 自动化回归

- 后端冻结运行环境：355 passed，5 skipped（skip为既有条件项）。
- 根目录验收/安装/工具：16 passed。
- Avatar worker：13 passed。
- 前端生产构建通过；Playwright：15 passed。
- 首次错误入口使用系统Python导致OpenCC缺失，并使用两个旧目录名；该记录不计为产品失败，也未删除。改用实际冻结venv和当前目录后全绿。

## PRD 规格检视

- FR-07/08：整句TTS和浏览器非静音播放30/30，无缓存混入。
- NFR-01：正式P95 4.878秒，满足用户批准的7秒门槛。
- NFR-03：未以额外模型常驻换延迟，资源低于既定RAM/VRAM门。
- UX7：仍为完整最终回复的一次CosyVoice调用；未恢复前缀/剩余文本碎片合成。
- 未签署项：打断、60分钟、Narrator、干净机和完整UX6仍保持开放，未由本报告冒充通过。

**开放 Critical=0，开放 Major=0；允许进入 RC1-AC04。**
