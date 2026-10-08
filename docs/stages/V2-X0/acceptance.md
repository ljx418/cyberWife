# V2-X0 验收标准

| ID | 操作 | 硬门 |
|---|---|---|
| X0-AC01 | 加载默认与本机覆盖配置 | `contracts=true`；其余V2-X flag=false；未知/非布尔flag拒绝 |
| X0-AC02 | 用合成source/appearance/scene/rendition构造manifest | schema、UUID、SHA、路径和引用全校验；路径穿越/绝对路径/重复ID拒绝 |
| X0-AC03 | stage→commit→load→下一revision→rollback | 原子提交；CAS冲突不改变active；rollback恢复字节等价上一revision |
| X0-AC04 | 同一V1 asset id重复执行bootstrap | 返回同一pack/source UUID和revision；不复制源文件、不改写ID |
| X0-AC05 | 在写入/替换前后注入故障 | active文件始终为旧合法版本或新合法版本，不出现半文件；staging可清理 |
| X0-AC06 | 生成证据摘要并扫描 | 无绝对路径、用户标签、原图/音频/记忆正文；只含版本、计数、哈希和布尔门 |
| X0-AC07 | 执行相关单元+配置回归 | 新测试全绿；既有runtime/asset/domain测试无回退；无需启动模型 |

出门后只开放X0.1计划，不签署V2X-AC01～15。
