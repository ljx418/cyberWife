# UX2 多写真生成与泛化验证

**执行日期：** 2026-10-05
**结论：** 3/3 技术链路通过；1/3 视觉建议可用，2/3 需要人工复核，不得把技术成功等同于视觉签署。

## 固定实验条件

- 输入：`C:\workSpace\videoWorkLine\testSource\图片-2.png`、`图片-1.png`、`图片-3.JPG`。
- 工作流：Wan2.2 I2V high/low 14B FP8 + LightX2V 4-step LoRA；seed 42。
- 输出：512×768、81 帧、16 FPS、5.061 秒；提示词按身份、姿态、配饰、服装、手势和背景保持编写。
- 每组在生成后使用生产 `build_video_avatar.py` 构建独立数据集；未写入活动 Avatar 数据库。

## 结果

| 样本 | 推理耗时 | 视频 SHA256 | 技术门 | 视觉审查 |
|---|---:|---|---|---|
| 图片-2（近景正脸） | 122.175s | `41a0758d...19e` | 81/81 帧、SCRFD、manifest 通过 | 身份/背景稳定；眨眼与笑容幅度较大，源图露齿使“严格闭嘴”不可满足；建议作为灵动档候选 |
| 图片-1（眼镜+手势遮挡） | 118.151s | `23d118e4...354` | 81/81 帧、SCRFD、manifest 通过 | 眼镜与身份总体稳定；手势位置显著变化且末段退出画面；必须人工复核 |
| 图片-3（侧脸+留白） | 116.143s | `222ca359...bfa` | 81/81 帧、SCRFD、manifest 通过 | 侧脸逐步转正，耳饰/姿态改变，末段出现新物体；不满足严格底片保持门 |

完整视频保存在：

- `C:\ComfyUI-aki-v2\ComfyUI\output\video\cyberWife\validation\image-2_wan22_idle_00001_.mp4`
- `C:\ComfyUI-aki-v2\ComfyUI\output\video\cyberWife\validation\image-1_wan22_idle_00001_.mp4`
- `C:\ComfyUI-aki-v2\ComfyUI\output\video\cyberWife\validation\image-3_wan22_idle_00001_.mp4`

本机结构化证据为 `audit/v1/UX2/multi-portrait-generation.json`，五帧组图位于 `audit/v1/UX2/contact-sheets/`；这些包含用户写真衍生物，不提交 Git。

## 对后续开发的约束

1. 自动门继续负责分辨率、FPS、帧数、单脸、脸框连续性、SHA 与可构建性；它不能签署身份与美术质量。
2. 源图露齿、近脸遮挡或大角度侧脸时，UI 必须提示风险，不得承诺严格闭嘴和姿态锁定。
3. “自然灵动”和“严格静息底片”应作为两个预设；不能用同一视觉阈值混为一谈。
4. 新物体、手势消失、配饰变形、姿态漂移继续保留为人工视觉门；未来若引入身份/分割/光流评分，只能辅助而不能替代人工签署。
5. 本批三组固定为泛化回归语料；后续改提示词、采样器、LoRA 或裁剪策略时必须同参重跑并与本报告比较。
