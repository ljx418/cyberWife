# UX5 阶段验收结果

**日期**：2026-10-05

**结论**：`PASS`——自动化硬证据通过；用户于2026-10-05明确认可此前开发工作并通过验收，UX5-AC06关闭。

## 真实实现与纠偏

1. 新增真实 H.264/PCM 采集器、相对错位分析器和公共 Oxford SyncNet 诊断包装器。
2. 首轮误用 20ms 实时 POST，使 Avatar 的10ms取包超时插入交替静音；纠正为与产品一致的 burst 输入后，相对分析恢复为0ms最佳。
3. Wav2Lip `batch_size` 由8降至4：真实推理仍远高于25FPS，首嘴型帧由约527ms降到冷/热218.060～370.307ms。
4. 浏览器对每个新turn首音频源预留295ms，冷/热四次绝对启动偏差为75.307、65.497、72.959、76.940ms，P95（最近秩）76.940ms。
5. 保留lower-face feather融合。上游整脸贴回对照没有提高公共SyncNet置信度，且会扩大眼镜/眼部重绘风险，未设为默认。

## AC逐项结论

| AC | 结果 | 证据摘要 |
|---|---|---|
| AC01 | PASS | 16kHz/mono/s16，182×640-byte，Avatar接收182，loopback |
| AC02 | PASS（自动门） | generation单调、0丢帧；295ms校准后启动偏差P95=76.940ms |
| AC03 | PASS（相对分析） | 最佳偏移0ms；0ms相关0.567465，高于±200/±400全部控制 |
| AC04 | PASS（自动门） | voiced/silent嘴部响应比1.383639；黑帧0；冻结帧对0 |
| AC05 | PASS | 四次inferfps最低144.569、finalfps最低25.642、总丢帧0；WS关闭后session释放 |
| AC06 | PASS（用户批准） | 用户审看真实输出后于2026-10-05认可并通过本阶段验收 |
| AC07 | PASS | 媒体只在gitignored audit/与私有目录；运行链仅127.0.0.1；许可证仍ResearchOnly |

## 公共 SyncNet 诊断说明

官方仓库的示例在本机得到 offset=3、confidence=10.081，与其README约值一致；工具安装有效。项目样本基线offset=-80ms，但confidence=0.654，且正向大错位控制在短语尾部不稳定，因此该公共模型对本样本只记为`INCONCLUSIVE`，不拿绝对分数签署或否决产品。发布门采用可复现的相对运动校准，同时保留人工感知门。

## 阶段门

UX5已签署PASS并允许继续后续计划。公共SyncNet诊断限制与Wav2Lip ResearchOnly许可证仍保留，不因本次体验批准而消失。

## 回归结果

- Backend：340 passed，4 skipped（既定平台/可选项跳过）。
- Avatar + UX5：14 passed，1 skipped。
- Frontend build：TypeScript + Vite PASS。
- Chromium Playwright：11/11 PASS，包含三视口、首音频排程、打断和黑屏回退。
- 出站白盒：PASS；活动运行代码无外部URL字面量，Avatar危险可选路由不可达。
- 阶段结束时六组件健康汇总为`ready`。
