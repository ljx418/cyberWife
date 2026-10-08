# V2-X1 验收标准

| ID | 操作 | 硬门 |
|---|---|---|
| X1-AC01 | 导入正面/侧面/全身/不同穿着至少4张真实格式图 | 每张source UUID、哈希、角度、标签、授权、来源完整；错误人物自动混入为0 |
| X1-AC02 | 重复上传同一文件 | source数量不增加，revision不伪增，返回同一source_id |
| X1-AC03 | 重启repository/API后读取 | pack_id/source_id/revision和顺序保持一致 |
| X1-AC04 | 读取缩略图/源图 | 仅按source_id；需有效写真授权；`Cache-Control: no-store, private`；响应不暴露路径 |
| X1-AC05 | 非法magic、角度、空标签、超限文件、路径注入 | 4xx；旧manifest字节及V1活动人物不变 |
| X1-AC06 | Manifest提交故障 | 新文件清理；上一active revision精确保留 |
| X1-AC07 | 使用设置页多选、逐张标注、上传、刷新 | 用户可见清单与API一致；上传不自动切换实时人物 |
| X1-AC08 | feature flag关闭 | UI隐藏/API拒绝；V1人物上传、生成和对话入口等价 |
| X1-AC09 | 全量回归 | 前端build/Playwright、后端pytest无新增失败 |

V2X-AC01要求最终用同一授权人物的4张真实照片做目标机人工核验；自动化使用真实PNG/JPEG编码和文件系统，不代签人物一致性的人工判断。
