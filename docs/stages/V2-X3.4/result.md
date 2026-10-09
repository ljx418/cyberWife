# V2-X3.4 实施结果

## 当前结论

**AUTOMATED PASS / WAITING HUMAN X3.4-AC08。** 第二外观的三场景关键帧、Idle、MuseTalk 候选和真实音频口播均完成机器验收；候选保持 `staged` 且 `visual_approved=false`，当前红色外观和活动场景未改变。

## 真实产物

- appearance id：`e52e9c41-abb5-5fa3-9297-d49297006c2a`
- 标签：`蓝白碎花上衣`
- 私有根：`~/.cyberWife/acceptance/V2-X3.4/blue-white-floral/`
- 审查页：`review/review.html`
- 3 张 1536×864 完整场景关键帧；3 段 160 帧/16fps/10秒完整场景 Idle。
- 3 套 250 帧 MuseTalk 1.5 staged 数据集；同一 8 秒真实 PCM 输入逐场景完成口播捕获。

## 自动门摘要

| 场景 | 首尾MAE | 脸中心P95 | 脸面积CV | 首视频包 | 音频响应比 | 黑帧 | 最大连续近冻结 | 结果 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 花园阳光房 | 2.7214 | 0.2837% | 1.2458% | 603ms | 1.2565 | 0 | 2 | PASS |
| 清晨卧室 | 2.0106 | 0.2538% | 0.5904% | 518ms | 1.2337 | 0 | 0 | PASS |
| 雨夜书房 | 1.9706 | 0.3452% | 0.9325% | 478ms | 1.2993 | 0 | 2 | PASS |

全部生成与捕获仅走本机路径/loopback；没有抠图、透明层或第二人物。自动指标不能证明身份相似和嘴型自然，因此未代签人工门。

## 回归与运行态恢复

- 根目录：62 passed。
- 后端：412 passed，7 skipped。
- Avatar：18 passed。
- Chrome/Playwright：51 passed。
- 前端生产构建：PASS。
- 生成后已恢复原红色形象 `musetalk15_idle_p_7ecfeecee271a502_9287499f_scenev2`；LLM、Speech、Avatar、Gateway 均重新探测为 healthy。
