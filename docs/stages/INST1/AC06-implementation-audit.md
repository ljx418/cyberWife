# INST1-AC06 实施后审计

**日期**：2026-10-06
**结论**：历史初审，后续发现可移植性缺口，已由AC06R取代；正式新环境执行OPEN。

| 审计项 | 结果 | 说明 |
|---|---|---|
| 防当前机冒签 | PASS | Windows SID哈希与WSL machine-id哈希分别拒绝；任一相同即写入前失败 |
| 防WSL克隆 | PASS | machine-id相同即失败，不因换Windows用户绕过 |
| 干净前置 | PASS | 数据根、两个venv、runtime config四项必须全部不存在 |
| 离线依赖 | PASS BY DESIGN | 正式入口只传`DependencyMode=wheelhouse`，不暴露online安装路径 |
| 工件归因 | PASS | 绑定workspace revision、wheelhouse manifest SHA256和CosyVoice revision |
| 生命周期 | PASS BY DESIGN | 固定start×2、status、Avatar recover、stop×2；每个运行态节点重新探测五个健康端点 |
| 失败清理 | PASS | lifecycle开始后finally再执行受管stop×2；沿用PID所有权门，不结束外部进程 |
| 报告隐私 | PASS | 只记录身份哈希、版本、布尔状态、步骤和通用错误；不记录身份原文、用户名或工件路径 |
| 当前机负例 | PASS | 当前身份拒绝后退出1；runtime config mtime不变 |
| 正式复现 | OPEN | 缺新Windows用户+新WSL环境，未冒签 |

本文件记录的是初版审查。后续查明“注册表存在”并不等于可移植、缺省Avatar未发布、Gateway仍依赖开发机私有音频，因此初版不得用于正式签署。修复与新结论见`AC06R-implementation-audit.md`。
