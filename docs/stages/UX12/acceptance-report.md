# UX12 自动验收报告

验收对象为 `direct_complete_scene` V5 候选。工作流 SHA-256 为 `27a19e9fca98b03f8b57c7c23acbe12a5006ac6336d8d26c588e6a4813fbeae0`。

## 证据链

- 生成 manifest：`~/.cyberWife/acceptance/UX12-direct-scene/videos-v5-final/manifest.json`
- 背景与关键帧：`~/.cyberWife/acceptance/UX12-direct-scene/`
- 三段视频与七时点抽帧：`~/.cyberWife/acceptance/UX12-direct-scene/videos-v5-final/`
- 工作流：`ops/comfy_avatar_fullscene_idle_api.json`
- 执行器：`ops/fullscene_idle_pipeline.py`
- 专项测试：`tests/test_fullscene_idle_pipeline.py`，3/3 通过。

## 白盒结论

视频主链为完整场景关键帧 → Wan 首尾帧条件 → 完整场景视频 → 全帧闭环处理。不存在前景人物分割、Alpha 蒙版、发丝抠像、人物边缘羽化或背景贴合步骤。

## 运行态恢复

生成结束后 Avatar `8010/8011`、语音 `8091`、LLM `8090` 均直接健康；网关进程在运行。网关聚合健康快照一度保留重启期间的旧错误状态，因此以各组件直接健康接口作为本轮恢复证据，不把旧快照写成全绿。

## 人工待验

请重点播放检查：人物是否像同一个人、10 秒末尾是否有“吸回去”的感觉、沙发接触是否自然、站立姿势是否仍显僵硬。任何一项不合格都不激活到当前 Avatar。
