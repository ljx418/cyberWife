# V2-X3.4-R2 实施后审计

## 审计意见

**Sound with one human-review finding。无新增致命或重大规格偏差。**

| 发现 | 严重度 | 证据 | 处置 |
|---|---|---|---|
| R1把尾静音标为说话且验收截断 | High（已修复） | 三场景R1末段反例 | PCM状态、complete协议、严格时长与末段硬门已闭环 |
| 全片冻结门与自然闭嘴冲突 | Medium（已修复） | R2花房7.52～7.68秒Idle近静止 | 有声冻结与末段稳定分门治理，保留全片诊断值 |
| 雨夜末段二阶比值0.956 | Low/人工关注 | R2真实采集 | 未超过有声段且其他门全过；要求R2-AC08人工观察 |
| 临时产品探针误将逐轮指标当累计值 | Info（已修正） | 指标按`media/open`逐轮重置 | 修正探针后六轮重跑PASS、退出码0 |
| complete最初位于TTS分段边界 | High（已修复） | 提前前缀与正文可能调用两次stream | complete上移到TurnPipeline整轮边界；轮级单测与真实链路通过 |
| 迟到或重复complete可能影响新一轮 | High（已修复） | 初版端点无generation状态检查 | Avatar记录活动/已完成generation并拒绝旧轮、重复控制与迟到PCM |

## 架构一致性

- Gateway仍是音频主时钟，Avatar只接收同一PCM及完成控制，不修改声音。
- `complete`不替代`cancel`，未破坏打断generation隔离。
- MuseTalk批大小、权重、坐标稳定数据集和显存驻留不变。
- 正式红衣形象已恢复；R2逻辑为模型无关的Avatar收尾能力。
- 当前审计由实现方内部执行，不冒充外部独立模型审计；人工视觉门仍保留。
