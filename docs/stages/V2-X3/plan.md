# V2-X3 开发计划：外观与场景预设

## 用户结果

用户可在当前角色下切换至少3个已登记背景场景与2个由多源素材归组的已确认外观；切换不结束当前会话，失败时保持上一选择，刷新和服务重启后仍恢复同一预设。

## 实现范围

1. `ScenePresetService`把四个内置背景以稳定UUID、真实文件SHA、焦点和安全区登记进现有experience manifest。
2. `SourcePackService`把相同用户穿着标签的source归为appearance；仅用户已确认标签可创建预设。
3. 场景/外观激活使用manifest revision CAS，一次提交一个新active组合；不存在或未确认引用拒绝。
4. API只返回稳定ID、标签、质量状态和公开背景URL，不暴露私有源图路径。
5. 前端切换先请求后端提交，成功后再更新舞台；失败保持旧画面并显示错误，不重置session/turn。
6. 当前Idle若存在同scene预合成则使用；缺失时明确回退“背景+当前人物”单舞台，不显示黑帧或第二人物。
7. feature flag关闭时沿用X2以前的本地背景选择，不迁移或删除既有偏好。

## 不做

- 不运行时文本换装，不生成新图片/视频。
- 不引入多角色、多空间并发或V2-A的ActiveContext。
- 不把同标签但不同人物自动合并；X3仍只接受当前source-pack。

## 交付实体

- `ScenePresetService`与source-pack appearance/scene事务
- scene/appearance API和设置页预设控制
- 真实背景哈希、CAS冲突、失败回退、重启恢复测试
- 阶段审计、PRD检视与架构同步

## 回滚

关闭`features.scene_presets`恢复原本地背景入口；manifest保留但不驱动舞台，V1/X2人物和会话链不变。

## 开发前审计发现的阶段门冲突

当前没有两套同时覆盖Idle与说话态的已批准外观rendition。项目所有者已批准拆为`X3A场景预设 → X4生成并批准两套外观rendition → X3B外观激活`；但后续真实数据复核发现其余三个场景同样缺少说话态完整场景rendition。为避免开口时跳回旧背景，推荐细化为`X3A0目录/CAS → X4S场景rendition → X3A1激活 → X4A外观rendition → X3B组合`。详见`scene-speaking-surface-audit.md`；批准细化前X3保持BLOCKED。
