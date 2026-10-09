# V2-X3.5 实施结果

## 结论

**PASS / COMPLETE。** 当前人物的红色针织上衣与蓝白碎花上衣已登记为2个已确认外观；清晨卧室、雨夜书房、花园阳光房形成6个共同可用组合，红衣额外保留蓝调客厅，共7个可逆绑定。默认已恢复为红衣×蓝调客厅。

## 实现事实

- 私有绑定升级为`scene-bindings.v2.json`，以`appearance_id + scene_id`唯一定位Idle和MuseTalk talking资产；原v1绑定未删除。
- source-pack revision 27同时保存两个confirmed appearance、活动appearance/scene及14条精确rendition记录。
- 激活接口以一次CAS提交外观和场景；错revision、缺文件、错SHA、重复组合及未确认外观均失败关闭。
- 设置页显示2个已批准外观；选择外观后只开放实际存在的场景组合，服务端提交成功后才更新主舞台。
- 安装器可重复执行且revision保持27，不会覆盖用户当前组合或重复登记资产。

## 真实运行证据

`/home/administrator/.cyberWife/acceptance/V2-X3.5/combinations/result.json`记录6/6共同组合使用同一8秒真实PCM的捕获结果：

- 首视频响应423.158～650.426ms；
- 每组168个MuseTalk推理帧，final FPS 25.430～25.730；
- 每组`audio_completion_ack=true`、`audio_completions=1`、序列缺口0；
- Gateway与Avatar重启后，蓝白碎花×清晨卧室仍恢复为同一appearance/scene/avatar；复验后恢复默认红衣×蓝调客厅。

## 回归

- Backend：418 passed，7 skipped。
- 根级：65 passed。
- Avatar：26 passed。
- Playwright：52 passed。
- 前端生产构建：PASS。
