# V2-X8.0 实施审计

## 白盒结论

| 检查 | 结果 | 证据 |
|---|---|---|
| 当前链是否是人物抠图 | PASS | 完整场景帧始终保留；Wav2Lip/MuseTalk都只在原帧人脸区域内融合 |
| 整脸输入假设 | PASS | Wav2Lip原本已输入完整脸框；`full`只改变输出覆盖，已由同输入失败数据拒绝 |
| 候选隔离 | PASS | 独立venv、模型根、avatar ID；manifest `active=false`；活动绑定未改 |
| 实时与资源 | PASS | MuseTalk inferfps58.457、finalfps25.459、VRAM约15.95GiB；黑帧/缺口/持续冻结0 |
| 可恢复 | PASS | canary后Wav2Lip Avatar和Gateway恢复healthy，活动API仍为`scenev2_mouth` |
| 自动冒签自然度 | PASS | 报告保持`WAITING HUMAN AC06`，机器相关性不替代音素/观感 |
| 许可证/保留 | PASS FOR CANARY | MuseTalk与face parser/VAE为MIT、Whisper为Apache-2.0、torchvision为BSD-3-Clause；精确路径/SHA已进入ComfyUI候选保留工作流，不进V1发布冻结 |

P0=0，运行安全相关P1=0。开放项只剩人工体验门与正式迁移，不否定canary自动化结果。
