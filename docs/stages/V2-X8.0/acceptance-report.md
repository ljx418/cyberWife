# V2-X8.0 验收报告

| 验收项 | 状态 | 结论 |
|---|---|---|
| AC01 任务链白盒 | PASS | PCM→特征→256脸区生成→原场景融合→H.264→Chrome实体全部定位；非人物抠图 |
| AC02 Wav2Lip融合A/B | PASS | 同输入、同帧、25fps；口周与整脸均实采，未覆盖active |
| AC03 整脸质量门 | REJECTED AS DESIGNED | 边界P95约4.2倍、锐度-12.7%；`full`不进入人工门 |
| AC04 模型事实审计 | PASS | MuseTalk/LiveTalking/Wav2Lip/Duix/LatentSync能力、许可与实时边界已区分；`livetalking-musetalk15`已按精确路径、SHA和候选状态进入ComfyUI保留合同 |
| AC05 MuseTalk串行canary | PASS | 250帧当前人物、真实8秒音频、finalfps25.459、黑帧/缺口/持续冻结0、资源未越界、已恢复Wav2Lip |
| AC06 同人物盲评 | WAITING HUMAN | 审查页已生成；同步、自然度、身份、清晰度须逐项≥4/5且不低于A |

阶段出门状态：**AUTOMATION PASS / WAITING HUMAN AC06。** 当前自动化开发停止点是高风险默认模型迁移的人类体验门，不是实现或环境阻塞。

## 回归证据

| 测试面 | 结果 |
|---|---:|
| UX5口型分析单元测试 | 5 passed |
| Avatar定向回归 | 18 passed |
| 后端定向回归 | 12 passed |
| 根目录全量测试 | 62 passed |
| 后端全量测试 | 407 passed, 7 skipped |
| 前端生产构建 | PASS |
| acceptance-core | 4 passed |
| Playwright真实浏览器回归 | 51 passed |

首次把根目录与后端两个pytest集合放在同一进程执行时出现同名`tests`包收集冲突；按各自项目根独立执行后全部通过。这是测试装载边界，不是产品功能失败，也未将失败批次冒充通过。

## 模型保留合同核验

- 工作流：`15_Avatar_MuseTalk15_串行候选验证.json`，logical ID=`livetalking-musetalk15`，状态=`candidate_human_gate`，明确禁止与Wav2Lip双常驻。
- 总索引：`00_项目模型保留索引.json`同时出现在`covered_logical_ids`与`protected_models`。
- 主工件：`musetalkV15/unet.pth`，3,400,074,924 bytes，SHA256=`7ebf6c98c181e20838e4c0054e96e944ac60d5d692cc01db42839fe11b787007`，实盘复算一致。
