# V2-X3.3 验收标准

| ID | 用户操作/故障 | 硬门 |
|---|---|---|
| X3.3-AC01 | 安装四个场景绑定 | 每场景同时存在批准Idle与talking rendition；视频/Avatar/清单SHA一致；每个Wav2Lip数据集160帧且完整场景 |
| X3.3-AC02 | 在设置页依次激活四个场景 | API revision逐次+1；目录准确显示活动项；错误场景、错误Avatar或不可激活项为0 |
| X3.3-AC03 | 保持同一对话session，在Idle/聆听态切换三次并继续说话 | `session_ref`与next turn不中断；只重连Avatar；切换期间同场景Idle托底；黑帧、双人物、旧背景说话为0 |
| X3.3-AC04 | 刷新页面并重启Gateway/Avatar | 恢复同一`active_scene_id`、Idle URL和`speaking_avatar_id`；无需重新选择 |
| X3.3-AC05 | 注入旧revision、缺失绑定、篡改SHA和Avatar不可加载 | 全部拒绝且活动scene/revision不变；浏览器保持上一可用画面或明确Idle降级 |
| X3.3-AC06 | 三个新增场景各输入同一真实测试音频并检查输出 | 嘴部像素真实响应音频；人物/服装/背景保持对应场景；单人物、无黑帧；动态自然度由人类批准 |
| X3.3-AC07 | 全量回归与PRD检视 | 后端、根工作流、Playwright、生产构建无新增失败；V1首响/打断/连续会话合同不回退 |

AC01～05及AC07可自动签署；AC06中的嘴部响应可自动量化，但自然度、身份与场景主观一致性必须由项目所有者批准。
