# V2-X1 自动化验收报告

**自动化结论**：X1-AC01～09的可自动化部分PASS  
**V2X-AC01真人一致性部分**：PENDING HUMAN

| 证据 | 结果 |
|---|---|
| 四图真实文件链 | 4个有效PNG编码→私有文件→manifest→API→浏览器清单，revision 1→4 |
| 元数据 | UUID、SHA-256、front/left/full_body/right、用户穿着标签、consent、local_upload、RFC3339完整 |
| 幂等 | 同字节二次上传created=false、source_id/revision/文件数不变 |
| 重启 | 新repository/API实例读取pack_id、4个source_id、revision及顺序完全一致 |
| 私有内容 | source_id读取字节一致；`Cache-Control: no-store, private`；响应无路径 |
| 错误与补偿 | 非图像、非法角度、超限、注入CAS冲突均不改变旧manifest；新文件清理 |
| V1迁移 | 活动写真稳定映射为v1_active_asset，V1 active id不变 |
| 前端旅程 | 多选2图、逐张标注、串行上传、缩略图和flag降级2/2 PASS |
| 前端全量 | build PASS；Playwright 42/42 PASS（4 workers） |
| 后端全量 | pytest 398 passed、7 skipped；无新增失败 |

自动化使用真实有效PNG编码和真实文件系统，不使用仅magic伪造的验收数据；但纯色测试图不能证明“同一授权人物未混入错误照片”，最终必须用用户的4张真人素材人工检查。
