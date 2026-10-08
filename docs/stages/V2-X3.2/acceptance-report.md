# V2-X3.2 验收报告

| 验收项 | 状态 | 证据/说明 |
|---|---|---|
| AC01 本机三关键帧 | PASS | `local-keyframes-v3/manifest.json`；1536×864，三张均单人脸且超过180px硬门 |
| AC02 本机三段Idle | PASS | `local-idles-v1/manifest.json`；每段160帧/16fps/10秒，无黑帧，首尾MAE≤3 |
| AC03 动作量 | PASS（自动部分） | 脸中心P95最大0.2893%，面积CV最大0.9237%；大幅肢体动作仍由AC06确认 |
| AC04 隐私与架构 | PASS | Comfy监听127.0.0.1；`matting=false`；未安装候选，活动场景未变 |
| AC05 故障注入 | PASS | 两轮小脸候选被拒绝；不产生approved状态；服务由finally恢复 |
| AC06 人工逐段播放 | WAITING HUMAN | 自动系统不代签动态自然度、身份一致性与主观循环体验 |
| AC07 全量回归 | PENDING | 人工批准后执行，避免为未批准素材提前签署阶段PASS |

阶段状态：**WAITING HUMAN，禁止进入 X3.3 场景激活。**
