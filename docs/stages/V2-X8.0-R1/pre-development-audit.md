# V2-X8.0-R1 开发前审计

## 结论

**允许进入开发。** X8.0同人物同音频canary已经证明MuseTalk finalfps=25.459、组合VRAM约15.95GiB、RAM约12.35GiB，未突破24GiB显存和16GiB空闲内存预算；项目所有者明确选择B。浏览器协议与Gateway会话协议无需变化。

## 风险闭环

| 风险 | 等级 | 关闭措施 | 状态 |
|---|---|---|---|
| 只迁移活动场景导致其他场景不可说话 | P0 | 四场景全部构建并以单一manifest原子切换 | CLOSED FOR ENTRY |
| 两模型常驻突破资源 | P1 | supervisor单引擎进程；切换必须停旧启新 | CLOSED FOR ENTRY |
| 数据集与引擎不匹配 | P1 | binding/manifest/health三处都声明engine并启动前校验 | CLOSED FOR ENTRY |
| MuseTalk失败后无法恢复 | P1 | 绑定与bootstrap备份、Wav2Lip工件不删除、真实回滚演练 | CLOSED FOR ENTRY |
| 其他人物被错误代签 | P1 | 人工批准仅覆盖当前人物；多形象逐素材验收留在后续阶段 | CLOSED FOR ENTRY |

未发现新增致命或重大未闭环风险。
