# UX2 候选报告：Wan2.2 闭嘴微动底片

**日期：** 2026-10-05  
**结论：实现完成、候选生成成功，视觉门暂不签署。**

## 已完成

- ComfyUI 工作流：`项目工作流总库/08_实时交互验证/09_Avatar_Wan22_闭嘴微动底片_5s.json`。
- API 工作流：`ops/comfy_avatar_idle_api.json`。
- 真实执行：Wan2.2 high/low FP8 + 对应 LightX2V LoRA，512×768、81 帧、16fps、5.061 秒，执行 119.63 秒。
- 输出：`C:\ComfyUI-aki-v2\ComfyUI\output\video\cyberWife\avatar_idle_wan22_c0cf2628_00001_.mp4`。
- 视频 SHA256：`c84ccd639a958c48f93ca961313623f3d413ca1c53c881febe426e5476e8f6a2`。
- 81/81 帧通过 SCRFD 单人脸检测；数据集构建成功；检测框连续；写真 SHA 写入 manifest。
- 模型保留索引已扩为 14 个精确 logical_id，覆盖 Wan high/low、LoRA、UMT5、VAE 和 SCRFD。

## 未通过项

源写真嘴唇本来略微分开；候选片尾仍有轻微唇形变化。虽然没有说话、露齿、切镜、新人物或明显身份漂移，但不满足“全程完全闭嘴”的严格字面门槛。因此：

- 未把候选视频升级为活动 Avatar；当前仍使用已验证的同源静态数据集。
- UX2-AC01、AC03、AC04 保持 PENDING，不能宣称动态待机体验已经交付。
- 技术实现已具备人工批准后原子升级能力；未批准时不会破坏现有体验。
