# UX6 开发计划：真实交互视觉修复

**日期**：2026-10-05  
**状态**：Crop V2 已获批准并激活；等待激活后的完整人工交互复验  
**基线证据**：用户截图 `1818×2406`；首响可接受、声音自然度 3.5/5、口型同步 0/5、Idle 自然度 2/5；结束对话后未持续播放 Idle

## 目标体验

当前激活人物在主舞台中保持完整、稳定且不遮挡主要文案；未说话时持续播放已人工批准的 10 秒闭环 Idle；说话时切换到同一人物的实时口型，结束或停止后无黑帧地回到 Idle。口型必须针对当前激活人物重新采集和人工验收，禁止继承另一人物样片的主观签署。

## PRD 边界

- 修复 FR-10（音画同步、Avatar 降级不丢结果）和 FR-16（三种视口可用）的真实体验偏差。
- 保持 G-UX 的主操作、路由、设置抽屉和六态不变；只修媒体层、构图和状态切换。
- 不改变 NFR-01 首响、NFR-02 资源/FPS、NFR-04 本机隐私和 Wav2Lip 私人非商业边界。
- 不引入公网模型、云端上传、第二套常驻 Avatar 或额外 GPU 常驻。

## 实施顺序

1. 把 active avatar 的 Idle 视频地址接入主舞台，静态人物仅作加载/故障兜底。
2. 建立三层媒体舞台：模糊填充背景、右侧等比人物层、实时 Canvas；所有层使用同一构图规则。
3. 状态切换固定为 `Idle video → live canvas → Idle video`，停止会话只关闭实时会话，不清除或暂停 Idle。
4. 为 1920×1080、1366×768、420×720 和用户实际 1818×2406 视口新增像素级截图与边界断言。
5. 使用当前 active avatar 与同一授权 CosyVoice WAV 重新采集真实 H.264 口型；分别评估时钟、嘴部形状、融合边界和静音恢复。
6. 若当前 Wav2Lip 输出仍不自然，按低冲击顺序比较：融合区域参数 → 人脸裁切/下巴 padding → `lower/full` 融合；只有当前人物真实视频胜出才可切换默认。实测根因是旧框把脖颈/背景压入模型输入，最终采用检测框 + 10px 下巴 padding、256px 模型输入的 Crop V2。
7. 重跑前端、Avatar、真实链路回归并交付当前人物视频给用户复验。

## 代码实体

| 实体 | 当前问题 | UX6 动作 |
|---|---|---|
| `prototype/src/App.tsx` | Idle 仅在设置预览；停止时只剩静态图 | 接入 active derivative 的 Idle URL及媒体状态 |
| `prototype/src/styles.css` | 竖版素材以 `cover` 铺满，导致脸部极端放大 | 统一 backdrop/contain 人物层与视口规则 |
| `prototype/src/services/AvatarSession.ts` | 实时 Canvas 停止后清空，无 Idle 接替合同 | 保持 Canvas 只负责 live；由舞台层无缝接替 |
| `tests/ux5/capture_lipsync.py` | 旧证据人物不是当前激活人物 | 复用采集器，证据绑定 active avatar id/source hash |
| `workers/avatar/utils/image.py` | lower-face 融合仅有机器运动相关证据 | 在当前人物上做可回退 A/B，不盲改默认 |
| `ops/build_video_avatar.py` | 旧裁切框过大；工件地址不含生成器版本 | Crop V2 紧裁切；地址加入 `cropv2`，旧工件不覆盖且可回退 |
| `prototype/tests/ux6-live-idle.mjs` | 缺真实页面 live→Idle 证据 | Headless Chrome 连接真实 Avatar 后点击结束并记录截图/时间推进 |

## 回退与停线

- Idle 视频加载失败：显示同源静态人物，不显示纯黑；报告 degraded。
- 当前人物口型人工评分仍低于 4/5：UX6 保持 FAIL，不得恢复 UX5/V1 全绿；可保留语音+Idle 降级。
- 任一方案增加首响超过 7 秒、Avatar 低于 25 FPS、VRAM 超过 22GB或破坏打断：立即回退该方案。
