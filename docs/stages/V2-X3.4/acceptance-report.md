# V2-X3.4 自动验收报告

| 验收项 | 结果 | 证据 |
|---|---|---|
| AC01 来源与身份隔离 | PASS | 未使用三张不同人物测试图；使用已批准正脸帧作为生成锚点，manifest 记录 SHA |
| AC02 三场景关键帧 | PASS | 3×1536×864、单人脸、正脸、蓝白碎花上衣、完整场景 |
| AC03 10秒低幅Idle | PASS | 3×160帧；黑帧0；接缝和脸部运动均低于门槛 |
| AC04 真实音频口播 | PASS | 固定8秒PCM SHA=`5cba0620...0340`；3/3嘴部响应，0黑帧，最大冻结≤2 |
| AC05 资产链 | PASS | keyframe/idle/candidate/capture manifest 与 SHA 齐全；候选 staged |
| AC06 故障保护 | PASS | 首轮侧脸候选被人工事实检视拒绝，未继续生成；未批准候选不能激活 |
| AC07 资源与隐私 | PASS | 重型模型串行；ComfyUI与Avatar均loopback；生成后实时服务恢复 |
| AC08 人工自然度 | PENDING | 必须观看私有 `review/review.html` 后由项目所有者决定 |
| AC09 回归 | PASS | 根目录62、后端412（7 skipped）、Avatar 18、Playwright 51全部通过；前端生产构建通过 |

**阶段门：未通过。** 原因仅为 AC08 尚未由人签署，并非机器测试失败。
