# V1FINAL 验收标准

| ID | 场景 | 出门门槛 |
|---|---|---|
| VF-AC01 | 无焦点授权调用现场验收器 | 启动前失败；Chrome、Narrator、麦克风均不被打开 |
| VF-AC02 | 现场取证隐私 | 报告不含音频、字幕、回复正文、人物媒体或私有绝对路径 |
| VF-AC03 | 三轮物理麦克风对话 | 三个不同 turn 均出现 `transcript.final`、`reply.text.final`、音频分块、播放结束和回到 listening；真实输入帧增加且活动轨道≥1 |
| VF-AC04 | 一次说话打断与恢复 | `barge_in.detected`、`turn.cancelled` 均存在；取消后又有一轮完整回复；错误事件为0 |
| VF-AC05 | 当前人物绑定 | active avatar id 与浏览器 Avatar WebSocket 参数一致；实时 Canvas 曾进入 live，结束后 Idle 继续推进 |
| VF-AC06 | 人工感知 | Narrator 五任务全部为是；口型同步、嘴部自然度、Idle自然度均≥4/5；结束后持续Idle为是 |
| VF-AC07 | 文档一致性 | PRD、计划、架构、追踪矩阵和冻结文档对工程完成项、外部门与商业边界描述一致 |
| VF-AC08 | 部署可移植性边界 | V1至少通过INST1-AC07单机隔离门并显式记录同身份/内核/驱动限制；INST1-AC06独立干净机可作为更高保证替代 |
| VF-AC09 | 最终总门 | 发布冻结逐文件哈希、revision绑定现场报告、显式策略对应的部署报告全部PASS；缺失=PENDING，过期/伪造=FAIL |

现场门失败返回非零退出码并保留脱敏失败报告；失败不得改写为“基本通过”。
