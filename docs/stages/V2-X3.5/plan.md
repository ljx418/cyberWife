# V2-X3.5 开发计划：场景×外观组合预设

## 用户结果

把X3.3已批准的红衣完整场景和X3.4已批准的蓝白碎花完整场景登记为可选择的组合。用户在设置页先选外观、再选相容场景；切换后Idle与实时口播始终来自同一完整画面，当前对话不被重置，失败时保留旧组合。

## 实现边界

- 仍只有一个活动人物与一个活动组合，不引入V2-A的Character/Space聚合或多角色并发。
- 私有绑定从“scene→rendition”扩展为“appearance+scene→rendition”；旧v1绑定继续只读兼容。
- source-pack保存两个已确认appearance ID、活动appearance ID和全部获批rendition；组合绑定保存明确的appearance ID、scene ID、Idle SHA及talking manifest SHA。
- 激活以同一次manifest CAS提交`active_appearance_id + active_scene_id`，只把目标组合的两个rendition标记active。
- Idle读取与active Avatar解析都按当前组合，不允许只换背景、只换静态图或回退到另一外观。

## 实现顺序

1. 扩展source-pack应用服务，支持幂等登记appearance及组合原子激活。
2. 扩展ScenePresetService兼容v1和v2绑定，严格验证路径、SHA、已批准Avatar、appearance引用和组合唯一性。
3. 扩展REST合同与前端类型，目录返回外观清单、活动外观和与外观匹配的场景项。
4. 设置页新增已批准外观选择；切换外观默认保持当前场景，若组合不存在则明确禁用而非静默换人。
5. 新增安装器，把已人工批准的X3.4候选与现有红衣绑定原子登记；安装失败不得覆盖活动v1绑定。
6. 真实执行六组合切换、跨重启恢复、实时口播和故障回滚；最后恢复用户原活动组合。

## 回滚

- 保留`scene-bindings.v1.json`、source-pack revision历史和安装前v2绑定备份。
- 关闭`scene_presets` flag恢复V1入口；v2绑定无效时服务拒绝组合，不读取未验证资产。
- 激活失败不提交manifest；前端重新读取服务端权威状态并继续显示旧组合。

## 非目标

- 不开放任意文本换装、在线生成、多角色或导入导出。
- 不在本阶段重新训练/常驻第二Avatar引擎；全部组合使用已批准MuseTalk单实例串行切换。
- 不以机器哈希替代此前已经完成的外观自然度人工批准。
