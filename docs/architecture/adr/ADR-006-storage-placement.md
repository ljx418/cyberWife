# ADR-006：源码在 C 盘，运行数据原计划 WSL2 ext4；2026-09-23 修订改放 C 盘项目目录

## 状态
**Superseded by 2026-09-23 修订**

## 背景（原始）
项目路径由用户指定为 `C:\workSpace\cyberWife`。SQLite 和频繁小文件在 WSL 访问 Windows 挂载盘时可靠性与性能不理想，且真实素材不应与源码混放。

## 决策（原始 2026-09-22）
源码和文档保留 C 盘；SQLite、向量、私有资产、缓存和运行日志放入 WSL2 ext4 的专用数据根。模型可引用既有只读路径，避免在 100GB 预算内重复复制。

## 后果（原始）
运行 I/O 更稳定且敏感数据与 Git 分离；备份、迁移和启动器必须同时理解 Windows 与 WSL 路径，V2 迁移需做停机快照。

---

## 修订：2026-09-23（用户显式选择 A 方案）

### 修订理由
用户在 2026-09-23 Claude 对话中显式要求将写真与声音存到 `C:\workSpace\cyberWife\` 项目目录下（Windows 端可直接访问）。这是与原始 ADR-006 决策实质冲突的范围变更，按 PRD §11 修订流程记录。

### 修订后决策
- **写真**：存到 `C:\workSpace\cyberWife\assets\portrait\`
- **声音**：存到 `C:\workSpace\cyberWife\assets\voice\`
- **audit**：存到 `C:\workSpace\cyberWife\audit\.consent.json`
- **SQLite / 向量 / 日志**：仍存到 WSL2 ext4（不变）
- **模型权重**：仍存到原 ComfyUI / 工具目录（不变；M0 实测路径）

### 隐私风险与缓解
| 风险 | 缓解措施 |
|---|---|
| 写真与项目源码同根，`.gitignore` 必须严格 | `.gitignore` 显式排除 `assets/`、`audit/`、`.consent-backup/`、`*.png`、`*.wav`、`*.webm` |
| Windows Defender 自动索引 | 用户需在 Windows Defender 设置中排除 `C:\workSpace\cyberWife\assets\` |
| 文件权限可能被多用户访问 | 设置文件夹权限为单用户读写（M6 实测） |
| Windows 备份工具（含 OneDrive）可能外发 | 用户需排除 OneDrive 同步 |

### 路径映射表（修订后）

| 用途 | 修订前 | 修订后（2026-09-23） |
|---|---|---|
| 源码 + 文档 + 测试 + migrations | `C:\workSpace\cyberWife\` | 不变 |
| 写真 | `~/.cyberWife/assets/portrait/` (WSL ext4) | **`C:\workSpace\cyberWife\assets\portrait\`** |
| 声音 | `~/.cyberWife/assets/voice/` | **`C:\workSpace\cyberWife\assets\voice\`** |
| audit + salt | `~/.cyberWife/audit/` | **`C:\workSpace\cyberWife\audit\`** |
| 配置（明文） | `config/` (仓库) | 不变 |
| 配置（本机路径） | `config/model-registry.local.yaml` (Git ignore) | 不变 |
| 后端默认 `--assets-root` | `/home/administrator/.cyberWife/assets` | **`/mnt/c/workSpace/cyberWife/assets`** |

### 撤销
- 用户在 Settings → 人物 / 声音 → 撤销授权时，软禁用路径与原 ADR-006 一致（B 路径）
- 撤回文件**不立即删除**：30 天由 RetentionService 清理（**未来 M5 阶段实现**）
- 当前 M3 阶段：撤回仅 `active_assets.asset_id = NULL`，文件保留

### 影响范围
- ✅ 不破坏 M0-M3 全部 214 测试
- ✅ 不破坏 ADR-001~005/007
- ⚠️ **新增隐私风险**：写真进入项目目录，需依赖用户严格维护 `.gitignore` 与文件系统权限

### 同步变更
- `human-consent.md §2` 路径表已修订
- `.gitignore` 强化（`assets/**`、`audit/**`）
- `server.py` 默认 `--assets-root` 改 `/mnt/c/workSpace/cyberWife/assets`
- `model-registry.local.yaml` 路径改 Windows

### 审计
- `docs/M2-stretch-audit.md` §1 路径表已同步
- 用户 2026-09-23 显式选择 A 方案；本修订由该次对话触发
