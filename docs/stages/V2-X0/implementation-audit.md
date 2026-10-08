# V2-X0 实现后审计

**日期**：2026-10-08  
**结论**：PASS；开放Critical/P0/P1=0。

## 白盒结论

- `runtime_config.py`严格限定14个`v2x`布尔键，默认仅`contracts=true`；未知键和非布尔值启动即失败，不会静默启用能力。
- `SourcePackManifest`拒绝未知顶层/嵌套字段、非UUID、非SHA-256、绝对/穿越/反斜杠路径、无时区时间、重复ID和悬空引用。
- manifest故意没有`character_id`，保持V2-X单活动角色边界；`legacy_asset_id`只用于幂等迁移锚点。
- `JsonManifestRepository`使用同目录临时文件、flush/fsync、`os.replace`、文件锁、expected revision和staged SHA令牌。另一个writer替换staging时，旧提交者必然冲突而不是误提交。
- rollback读取已校验历史revision并原子恢复；写入失败时active仍是完整旧版本。
- `SourcePackService.bootstrap_from_v1`以legacy asset id+哈希生成稳定UUID，已有同一映射直接返回；不同legacy id拒绝。
- `contract_evidence`只输出flag、revision、计数和manifest哈希，不输出路径、标签、授权ID或资产内容。

## 依赖与范围

- application只依赖domain和port；infrastructure实现port；没有FastAPI/SQLite/MCP逆向渗入domain。
- 无新增API、UI、数据库迁移、网络访问或模型驻留；V1 active资产和实时链不读取X0 manifest。
- 未发现超出D1/PRD范围的多角色、多空间、插件或导入导出入口。

## 审计中修正

首版仓储只有revision CAS，白盒复查发现两个writer可在stage和commit之间覆盖共享staging。已增加staged SHA令牌和文件锁，并以交叉writer测试证明旧writer提交被拒绝。该P1已关闭后才执行全回归。
