# V2-X1 开发计划：多源形象素材

## 用户结果

用户可在同一个当前角色下连续导入正面、左侧、右侧、全身及不同穿着照片；每张照片都能查看缩略图、角度、穿着标签、来源、授权和哈希摘要。重启后清单仍保持一致，导入不会自动替换当前说话人物。

## 实现范围

1. 激活X0已冻结的`SourcePackManifest`、`SourcePackService`和`JsonManifestRepository`。
2. 增加source-pack读取、单张追加上传和按`source_id`读取私有内容的API。
3. 上传只接受真实JPEG/PNG、单文件≤20MiB；路径由服务端生成，客户端永不提交或获得绝对路径。
4. 每项记录UUID、SHA-256、角度、穿着标签、授权ID、`local_upload`来源和RFC3339时间。
5. 相同内容在同一pack中幂等，不创建重复source；不同照片顺序追加并以revision CAS提交。
6. Manifest提交失败时删除本次新文件，旧revision保持可读；源图内容始终`no-store, private`。
7. 设置页增加“素材”面板；支持多选文件后逐张确认元数据并显示真实本机缩略图。
8. feature flag关闭时API返回能力未启用、UI不出现，V1单图上传/当前人物链保持不变。

## 明确不做

- 不把多张照片自动混成人物模型，不自动切换活动人物。
- 不推断照片中不可见的身体、穿着、身份或关系事实。
- 不开放多角色ID、导入导出或删除传播；这些属于V2-A或后续明确阶段。
- 不让source-pack成为V1实时Avatar的双写权威；X1只管理输入素材清单。

## 交付实体

- 扩展`SourcePackService`追加/幂等合同
- `ApiGateway` source-pack API与server组合根注入
- `ConversationClient`和设置页`SourcePackPanel`
- 后端真实文件/Manifest集成测试、前端用户旅程测试
- 阶段审计、PRD检视、架构图和回滚证据

## 回滚

关闭`features.source_pack`即隐藏面板并拒绝新API；已有私有清单和源图不删除，V1 active portrait与Avatar不变。
