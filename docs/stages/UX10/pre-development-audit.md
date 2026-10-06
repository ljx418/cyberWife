# UX10 开发前审计

**日期**：2026-10-06
**结论**：开放Critical/Major=0；允许按UX10.1→UX10.4顺序进入实现。

| 风险 | 初始等级 | 闭环措施 | 入口状态 |
|---|---|---|---|
| 3840×180无法容纳普通主舞台全部内容 | Major | 明确采用条幅降级，只保留脸/肩安全区、单行字幕和核心语音操作；设置用覆盖层 | CLOSED |
| 背景和人物复用同一图导致白底/黑屏 | Major | 独立本地背景层，人物失败和背景失败各自回退；禁止公网URL | CLOSED |
| 生成背景引入人物/文字/事实错误 | Major | 仅生成无人物室内/自然场景，逐张视觉检查；测试只依赖本地最终资产 | CLOSED |
| Idle提示调整破坏已批准人物 | Critical | 新候选隔离生成，机器门+人工批准后才能原子激活；当前素材不自动覆盖 | CLOSED |
| 手工记忆绕过向量/删除事务 | Critical | 统一调用MemoryService和现有repository upsert/delete，不允许API直接写表 | CLOSED |
| 候选确认重复写或跨会话确认 | Major | 候选键绑定session/turn/content，确认幂等并校验所属会话 | CLOSED |
| 候选在确认前污染Prompt | Critical | candidates继续驻进程且不进入`recall()`；增加负向合同测试 | CLOSED |
| 新UI破坏可访问性或V1主操作 | Major | 新增键盘、axe、焦点和四视口旅程；不改变六态和主语音按钮语义 | CLOSED |
| 回归证据与代码revision不一致 | Major | UX10完成后重新执行V1FINAL核心和发布聚合；旧报告不冒充当前revision | CLOSED |

拒绝路线：不把背景和记忆塞进无版本、无来源的任意JSON；不在V1引入Character/Space聚合；不以CSS动画冒充低幅生成式Idle；不以Mock记忆替代真实SQLite/FTS/vector往返。
