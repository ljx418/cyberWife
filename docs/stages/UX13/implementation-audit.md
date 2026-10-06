# UX13 实施与验收审计

**日期**：2026-10-06
**结论**：UX13非说话态序列 PASS；V1实时口型门 REOPENED（用户报告说话视频嘴型似乎不变，必须通过AC-06A后才能出门）

## 1. 批准范围

批准对象是 `videos-v2-frontal/manifest.json` 所绑定的完整场景序列：开场走近、严格正脸半身低幅 Idle、结束走回并坐下。批准不扩展到 UX11 抠图路线、UX12 其他姿势候选，也不改变实时说话态 Wav2Lip 数据。

## 2. 实现实体

| 层 | 实体 | 已实现合同 |
|---|---|---|
| 安装门 | `ops/install_scene_sequence.py` | 必须显式提交 `UX13-FRONTAL-V2-APPROVED`；只选择当前 active derivative |
| 应用层 | `AvatarAssetService.install_approved_sequence` | 校验完整场景模式、禁止抠图、关键帧及三段视频 SHA-256、输入同目录；原子复制到私有 job 目录 |
| API | `GET /api/v1/avatar-builds/{id}/idle-generation/{intro|video|outro}` | 只返回 active/awaiting_approval job 内的私有文件；路径越界拒绝；响应 `private, no-store` |
| 前端 | `App.tsx` 的 `intro → idle → live avatar → outro` 状态 | 页面进入只播一次 intro；idle 循环；开始会话由实时 canvas 覆盖；正常停止播一次 outro 并停在坐姿末帧；异常与加载失败退回旧 Idle/静态图 |
| 样式 | `.idle-avatar-video--scene` | 完整场景铺满舞台并使用 `object-fit: cover`，不再叠加透明抠图边缘 |

实时说话态 active avatar 在安装前后均为 `wav2lip256_idle_p_7ecfeecee271a502_47cbb203_cropv2`；本阶段没有把 Idle 视频冒充口型同步，也没有替换其模型或工件。

## 3. 真实运行证据

运行 job：`/home/administrator/.cyberWife/avatar/idle-jobs/2/job.json`；安装前备份：`job.pre-ux13-frontal-v2.json`。

| 运行态对象 | SHA-256 | HTTP验证 |
|---|---|---|
| 正脸关键帧 | `5f7f0586b1082ad8455ca76c0409dc65991c407bc82e23425b852ef73cca6c31` | 1,996,278 bytes |
| Idle | `9287499f15384911df2501df7a6faf0c12f4a8905768166fe80f1c3d7da562d8` | 1,037,813 bytes |
| Intro | `999a48d3ebebf2f239e7c2e1c42e671c5a981f10e3412e8379dc119b8fd341be` | 788,015 bytes |
| Outro | `f1a0ef142293e33939cf520bf4b0646882c62e17f0a121c04703b77207830f7c` | 1,405,146 bytes |

Gateway 重启后 `/api/v1/avatar-builds/2/idle-generation` 返回 `status=active`、三个序列预览均为真、`sequence_version=ux13-frontal-5f7f0586b108`。Headless Chromium 直接访问实际 Gateway：intro `readyState=4`、无媒体错误、1440×900 全舞台 cover；派发真实 ended 事件后切换到 idle URL 且 `loop=true`，请求失败数为 0。随后用虚拟麦克风建立真实 Gateway 会话并点击正常结束，状态从会话期 `idle` 序列切换为 `outro`，结束片 `readyState=4`、`loop=false`、时长 5.0625 秒且无请求失败。

## 4. 回归结果

| 范围 | 结果 |
|---|---:|
| 后端全量 | 373 passed，7 skipped |
| 根目录工作流/素材测试 | 52 passed |
| 前端生产构建 | PASS |
| Playwright | 24 passed；含完整场景序列状态机、极端视口、键盘、可访问性、打断与 Idle 恢复 |

7 个 skip 为既有环境条件项，不由本阶段新增。真实语音、ASR、LLM、TTS、实时口型工件未被修改；它们此前的目标机证据继续有效，本轮全量后端回归未发现接口退化。

## 5. 风险与回退

- Intro/Outro 是视觉序列，不参与音频主时钟；实时说话仍由 WebSocket H.264 canvas 驱动。
- 浏览器禁止自动播放、文件损坏或任一序列请求失败时，前端撤销 sequence 标志并回退原有循环 Idle/静态人物，不阻断语音。
- 回退无需改数据库：恢复 `job.pre-ux13-frontal-v2.json` 并重启 Gateway 即可；已安装版本化文件可保留作审计，不会被旧 job 引用。
- 本阶段只证明单 active avatar 的非说话态场景序列接入；同场景说话态全身驱动、多形象和多空间仍属于 V2，不得标记完成。用户在后续交互中报告“当前视频对应的口型似乎一直没有变”，因此实时口型不得继承本阶段PASS，现按AC-06A单独阻断。

## 6. PRD 检视

本阶段增强 FR-10 的非说话态体验与停止恢复，不削弱 FR-01～20、NFR-01～10。它保持本地私有存储、无公网运行依赖、加载失败可降级和人工批准后才能安装四项既有约束。项目所有者的人工批准关闭 UX13 主观门；V1 总验收中的物理麦克风、Narrator 和整体现场报告仍是独立门，不能由本审计代签。
