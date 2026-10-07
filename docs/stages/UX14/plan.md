# UX14 实施计划：同场景单人物实时口型

**日期**：2026-10-07

## 用户场景

用户从已批准的完整场景Idle进入语音对话时，画面中始终只有同一个人物。背景、人物身份和摄影机机位不跳变；说话时嘴部在唯一主画面内变化，不再叠加另一套半身Avatar。

## 实施实体

1. `build_video_avatar.py`增加完整帧保留模式，按原始768×432场景建立Wav2Lip数据，不做竖版letterbox或人物抠图。
2. `AvatarAssetService.install_approved_sequence`将获批Idle同时提升为`scenev1`说话工件，并把`idle job / active derivative / socket avatar_id`绑定到同一ID。
3. `App.tsx`根据`single_surface_ready`选择完整场景呈现。
4. live首帧到达时Canvas铺满舞台并透明替换Idle；停止、异常或无实时帧时回退Idle。
5. 每次开始对话重新读取active avatar与idle job；ID变化时AvatarSession必须关闭旧连接并用新ID重连，不能沿用页面打开时的缓存。

## 风险门

- 不允许只靠CSS隐藏双人而继续使用不同人物底片。
- 不允许把Idle动作当成嘴部响应。
- 完整场景首尾MAE和折返点MAE均须≤3；人工批准不能豁免接缝门。
- 说话态黑帧、冻结、丢帧或同屏双人物均为FAIL。
- `presentation=portrait`、active/job/socket ID不一致或前端状态尚未提交时，Canvas必须隐藏并继续显示完整场景Idle，禁止右侧矩形遮罩。
