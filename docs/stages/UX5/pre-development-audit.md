# UX5 预开发审计

**日期**：2026-10-05  
**审计对象**：`plan.md`、`acceptance.md`、`prd-review.md` 与现有 Avatar 代码

## 审计结论

| 风险 | 严重度 | 闭环措施 | 状态 |
|---|---:|---|---|
| 历史 B2 用 FPS 代替口型正确性 | Major | 新增时间线、错位对照、嘴部动态与人工四层证据 | CLOSED |
| H.264 文档仍称 14-byte 帧头，代码实际为18-byte | Major | 采集器按 `version=2`/18-byte 解析；阶段完成同步实现合同 | CLOSED FOR ENTRY |
| 公共 SyncNet 权重与论文评估版本不可比 | Major | 只使用相对错位校准；绝对值不作硬门 | CLOSED |
| 能量相关性不能判断每个音素形状 | Major | 保留 AC06 人工感知门，自动化不得替代 | CLOSED |
| 真实素材或语音进入 Git | Critical | 全量媒体只写 `audit/`/私有目录，提交前 Git 扫描 | CLOSED |
| 验收采集占用 Avatar session 未释放 | Major | `finally` 关闭 WS，服务端 remove_session，验收后探针 | CLOSED |
| ComfyUI 与 Wav2Lip 并发导致显存越门 | Major | 禁止并发，先确认生成任务结束再采集 | CLOSED |

## 代码事实核查

- `/api/v1/media/{session}/audio` 已强制 `application/octet-stream`、640 bytes，并把 `clock_ms/generation` 送入 Avatar。
- `/ws/v1/avatar` 已限制 loopback peer 与 loopback Origin，可为指定 `avatar_id` 建立真实 render session。
- `BaseAvatar` 已把音频 generation 传到视频帧；H.264 输出在 generation 改变时强制关键帧。
- 当前缺口位于验收工具和感知证据，而不是需要重写产品协议。

## 阶段门

未发现新增 Critical 或未闭环 Major 风险。允许进入 UX5 实质开发；若自动化相对校准失败或真实视频人工评分低于 4/5，必须返回修复/备选模型评估，不得继续签署 V1 完成。
