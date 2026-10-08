# V2-X3.1 开发计划：场景目录

## 用户结果

用户在设置页能看到四个本机场景的真实登记状态，并明确知道哪些场景只有预览、哪些尚待动态素材；刷新和服务重启后场景ID不变化。

## 实现范围

1. 新增 `ScenePresetService`，从项目内四个背景文件计算真实SHA-256。
2. 以固定namespace和场景slug生成稳定UUID，并幂等写入现有source-pack manifest。
3. 目录包含label、预览URL、焦点、安全区和`preview_only`质量状态；API不返回文件系统路径。
4. `features.scene_presets=false`时API返回404，原V1/X2本地背景入口不变。
5. 设置页只读展示目录与“动态素材待准备”，不提供未满足质量门的激活操作。

## 明确不做

- 不切换Avatar数据集，不改变`active_scene_id`。
- 不运行生成模型，不把静态预览冒充Idle或说话态场景。
- 不创建外观、rendition或多角色实体。

## 回滚

关闭`features.scene_presets`即可隐藏目录；已登记manifest数据保留且不驱动舞台。

