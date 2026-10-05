# UX6 开发前审计

**日期**：2026-10-05  
**结论**：允许进入修复；开放 P1 三项，验收标准已能阻止旧样片和 FPS 造成的虚假通过。

## 证据核对

- 用户截图为 1818×2406，当前 512×768 竖版人物被全屏 `cover`，人物脸部明显过度放大且文案横跨眼部。
- `App.tsx` 只在设置页渲染 Idle `<video>`；主舞台只有静态 `.portrait` 和实时 `<canvas>`。
- `stopConversation()` 调用 `AvatarSession.stop()`，后者隐藏并清空 Canvas；主舞台没有 Idle 接替者。
- 当前 active avatar 为 `wav2lip256_idle_p_7ecfeecee271a502_47cbb203`，source hash 前缀 `7ecfee...`；既有 UX5 人工视频记录的是 `ux5_image1_160_validation`，不能继承主观签署。
- 本轮日志中 Wav2Lip 推理约 70～116 FPS，故口型 0 分不是吞吐不足的充分解释。

## 风险闭环

| 风险 | 等级 | 闭环方式 | 入口状态 |
|---|---|---|---|
| Idle 仍只在设置页播放 | P1 | AC01/02直接检查主舞台视频时间 | CLOSED IN PLAN |
| `cover` 修复后出现大面积空白 | P1 | 同源模糊背景 + 等比前景，不拉伸 | CLOSED IN PLAN |
| 旧人物视频冒充当前人物口型 | P1 | 证据强制绑定active id/source hash | CLOSED IN PLAN |
| 改融合损坏眼镜/身份 | P1 | current-avatar A/B + 可回退环境开关 | CLOSED IN PLAN |
| 自动指标再次掩盖主观失败 | P1 | AC06必须由用户重新评分 | CLOSED IN PLAN |

开放 Critical=0；未闭环 P1 已全部转为可执行验收门。可以开始代码修复，但阶段结论保持 FAIL，直至用户复验。

