# V2-X3.1 开发前审计

**结论**：PASS；P0/P1新增风险为0，可以进入实质开发。

- 复用source-pack manifest及revision CAS，不新增数据库或第二active指针。
- 背景是仓库内公开静态资产；只返回站内预览URL，不暴露宿主路径。
- 稳定UUID由固定namespace+slug生成，SHA从真实文件计算，不写假值。
- 本阶段不写`active_scene_id`，因此不会触发说话态场景不一致。
- 前端明确标记`preview_only`且禁用激活，避免把目录交付误报为动态场景切换。
- 不启动ComfyUI/Avatar生成任务，硬件资源冲击可忽略。

