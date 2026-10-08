# V2-X3.3 开发计划：场景激活

## 用户结果

用户可在“她的世界”中选择四个已批准场景。切换后，Idle 与说话态始终是同一人物、同一背景的单一完整画面；页面刷新和本机服务重启后恢复最后场景。切换不得新建或结束对话会话。

## 前置证据

- X3.1四场景目录、稳定UUID和SourcePack CAS已PASS。
- X3.2三套新增场景关键帧与10秒Idle已通过自动门和项目所有者人工动态审查。
- 蓝调客厅已有已批准UX13完整场景Idle、开场/退场序列和Wav2Lip数据集。

## 实现实体

1. `SceneRenditionInstaller`（离线安装器）：验证批准清单/SHA，复制私有Idle，调用现有`build_video_avatar.build(..., preserve_frame=True)`构建对应完整场景Wav2Lip数据集；全部输出通过后原子写入`scene-bindings.v1.json`。
2. `SourcePackService.register_renditions/activate_scene`：登记每个场景的`idle`和`talking`批准rendition；用调用方`expected_revision`执行CAS激活。
3. `ScenePresetService`：交叉核对SourcePack、绑定清单、Idle文件和Avatar数据集；只有全部一致才返回`can_activate=true`，并提供活动场景解析和私有Idle路径。
4. Gateway：新增`POST /api/v1/scene-presets/{scene_id}/activate`及私有Idle读取端点；`GET /api/v1/avatar/active`在活动场景存在时返回其`speaking_avatar_id`。
5. 前端：场景卡提供真实激活按钮和状态；切换成功后先显示同场景Idle，再重连Avatar；会话WebSocket、turn和音频链保持不变。思考/说话阶段禁用切换，Idle/聆听阶段允许，避免中途音频对应旧画面。

## 原子性与回退

- 安装失败只留下不可引用的孤立暂存/数据集，不写绑定、不改变活动场景。
- 激活前验证目标Idle和Avatar数据集；CAS冲突返回409，当前场景不变。
- Avatar重连失败时继续显示目标同场景Idle并给出降级提示；不出现黑屏或旧场景说话层。
- 删除/损坏绑定后`can_activate=false`，活动解析回退既有V1 Avatar，不伪造可用状态。

## 明确不做

- 不增加第二人物图层、抠像或实时背景合成。
- 不在X3.3生成新外观；X3.4负责外观动态素材。
- 不实现多Space/多Character领域管理；X3.3仍是单用户、单活动场景。
- 不在思考或说话音频进行中切换场景。
