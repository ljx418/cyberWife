# V2-X8.0-R1 实施审计

| 审计点 | 状态 | 证据结论 |
|---|---|---|
| 四场景完整覆盖 | PASS | 四个binding均为`engine=musetalk`，各250帧、768×432、25fps，manifest SHA与rendition一致 |
| 实时性能 | PASS | 四场景finalfps最低25.461；重启确认26.371；黑帧和序列缺口均0 |
| 口型真实响应 | PASS | 四场景及两次蓝调复测均有音频相关；最终两次蓝调连续性通过 |
| 资源硬门 | PASS | 峰值VRAM16.44/23.99GiB；WSL RAM13.72/15.53GiB；一个Linux Avatar模型进程 |
| 一键启动/健康 | PASS | `auto`解析MuseTalk bootstrap；Avatar/Gateway均报告`livetalking-musetalk15`、fp16和ready |
| 回滚真实性 | PASS | 实际切到Wav2Lip并全绿，再切回MuseTalk并全绿；revision 15→16 |
| PRD偏移 | PASS | 浏览器协议、单人物完整场景、声音、打断、首响上限均未修改 |
| V2-A收纳 | PASS | AvatarModelPolicy、兼容rendition、串行切换、失败保持旧上下文及V2A-AC08已落盘 |

未发现新增P0/P1风险。一次蓝调首次运行连续3个近冻结对已透明记录，返回复测后连续两轮通过；若人工使用中可重复观察到明显卡顿，应进入既定V2-X8.1质量治理，不回退本阶段事实记录。
