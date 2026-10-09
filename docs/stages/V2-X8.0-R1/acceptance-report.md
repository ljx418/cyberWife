# V2-X8.0-R1 验收报告

| 验收项 | 状态 | 结论 |
|---|---|---|
| AC01 四场景引擎/资产一致 | PASS | 4/4 MuseTalk binding与批准manifest一致，无人物/场景串位 |
| AC02 四场景真实8秒音频 | PASS AFTER RETEST | finalfps均≥25、黑帧/缺口0；蓝调首次连续性失败后两轮复测通过 |
| AC03 硬件资源 | PASS | 峰值VRAM16.44GiB、WSL RAM13.72GiB；未突破24/16GiB门，单模型常驻 |
| AC04 启动与恢复 | PASS | 默认auto启动MuseTalk；Avatar/Gateway/LLM/Speech全绿，活动场景一致 |
| AC05 Wav2Lip回滚 | PASS | 真实往返并恢复B；binding、rendition、bootstrap与健康engine一致 |
| AC06 回归/规格 | PASS | 62 + 410 + 18项Python、生产构建、51项Chrome回归通过；PRD无偏移 |

阶段出门状态：**PASS / ACTIVE。** 当前默认模型为MuseTalk 1.5；下一阶段可继续V2-X8.1音画质量治理。用户模型选择UI与角色级持久化明确留在V2-A，不在本阶段提前暴露未完成入口。
