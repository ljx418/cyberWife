# V2-X3.2 验收报告

| 验收项 | 状态 | 证据/说明 |
|---|---|---|
| AC01 本机三关键帧 | PASS | `local-keyframes-v3/manifest.json`；1536×864，三张均单人脸且超过180px硬门 |
| AC02 本机三段Idle | PASS | `local-idles-v1/manifest.json`；每段160帧/16fps/10秒，无黑帧，首尾MAE≤3 |
| AC03 动作量 | PASS | 脸中心P95最大0.2893%，面积CV最大0.9237%；项目所有者在AC06确认三段动态自然度通过 |
| AC04 隐私与架构 | PASS | Comfy监听127.0.0.1；`matting=false`；未安装候选，活动场景未变 |
| AC05 故障注入 | PASS | 两轮小脸候选被拒绝；不产生approved状态；服务由finally恢复 |
| AC06 人工逐段播放 | PASS | 2026-10-08项目所有者逐段审查后明确回复“三个视频挺好的，批准验收” |
| AC07 全量回归 | PASS | 后端405 passed/7 skipped；根工作流测试60 passed；Playwright 50/50；核心合同4/4；生产构建PASS |

阶段状态：**PASS，允许进入 X3.3 场景激活的文档门。**
