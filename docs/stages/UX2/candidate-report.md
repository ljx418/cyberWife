# UX2 候选报告：Wan2.2 闭嘴微动底片

**日期：** 2026-10-05  
**结论：实现完成；首个候选已由用户签署视觉门并激活；多写真泛化验证已完成。**

## 已完成

- ComfyUI 工作流：`项目工作流总库/08_实时交互验证/09_Avatar_Wan22_闭嘴微动底片_5s.json`。
- API 工作流：`ops/comfy_avatar_idle_api.json`。
- 真实执行：Wan2.2 high/low FP8 + 对应 LightX2V LoRA，512×768、81 帧、16fps、5.061 秒，执行 119.63 秒。
- 输出：`C:\ComfyUI-aki-v2\ComfyUI\output\video\cyberWife\avatar_idle_wan22_c0cf2628_00001_.mp4`。
- 视频 SHA256：`c84ccd639a958c48f93ca961313623f3d413ca1c53c881febe426e5476e8f6a2`。
- 81/81 帧通过 SCRFD 单人脸检测；数据集构建成功；检测框连续；写真 SHA 写入 manifest。
- 模型保留索引已扩为 14 个精确 logical_id，覆盖 Wan high/low、LoRA、UMT5、VAE 和 SCRFD。

## 人工签署与运行时激活

源写真嘴唇本来略微分开，候选片尾仍有轻微唇形变化，因此自动门没有代替人工签署。2026-10-05 用户明确确认视频效果良好并批准激活。系统随后执行原子升级：

- 活动 Avatar：`wav2lip256_idle_p_c0cf262891178703`；
- 运行时接口：81 帧、512×768，状态 `active`；
- Windows Chrome 154 Headless 实测：5 秒解码 191 帧、媒体 25 FPS、陈旧帧丢弃 0、停止后画布隐藏且无黑屏；
- 探针证据：`audit/v1/UX2/h264-dynamic-approved.json`（本机证据目录，不入库）。

## 多写真泛化验证

`图片-2.png`、`图片-1.png`、`图片-3.JPG` 均使用 seed 42、512×768、81 帧、16 FPS 的同一工作流生成，并全部通过 81 帧 SCRFD 数据集构建。视觉结论及视频路径见 `multi-portrait-validation.md`。这三组只作为回归语料，没有替换当前活动写真。
