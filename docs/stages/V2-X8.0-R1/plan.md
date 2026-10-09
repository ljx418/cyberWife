# V2-X8.0-R1 开发计划：MuseTalk正式迁移

## 目标

在项目所有者确认MuseTalk 1.5观感优于Wav2Lip256后，把B路线从单场景canary迁移为四个已批准场景均可使用的默认实时引擎。迁移必须保持单人物、完整场景、25fps、可回滚和单引擎常驻，不改变浏览器H.264协议。

## 实施范围

1. 为四个现有`scenev2_mouth`数据集生成对应MuseTalk VAE latent和jaw mask，复用原始250帧与已批准人脸框。
2. 场景绑定显式记录`engine`；ScenePresetService不再把活动引擎写死为Wav2Lip。
3. RuntimeLauncher增加`auto|wav2lip|musetalk`串行引擎选择，`auto`读取本机受控bootstrap策略；MuseTalk使用独立venv和固定模型根。
4. 原子备份并切换四场景绑定；bootstrap同时写入引擎和有效启动avatar ID。
5. 切换后重启Avatar/Gateway，执行四场景真实音频、资源、恢复和浏览器回归；任一硬门失败整体回滚。

## 非目标

- 不让Wav2Lip和MuseTalk双常驻。
- 不在本阶段交付用户模型选择界面；该能力进入V2-A的角色级`AvatarModelPolicy`。
- 不把单场景人工批准外推为其他人物形象批准；其他形象仍需独立质量门。

## 回滚

保留切换前场景绑定、bootstrap策略和Wav2Lip数据集。回滚只需恢复绑定与`avatar-engine=wav2lip`，重启Avatar/Gateway；MuseTalk派生工件保留供诊断，不删除用户资产。
