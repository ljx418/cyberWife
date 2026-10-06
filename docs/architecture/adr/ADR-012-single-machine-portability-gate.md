# ADR-012：V1 单机隔离可移植性门

**状态**：ACCEPTED  
**日期**：2026-10-06  
**决策人**：项目所有者（明确同意放宽第二台物理机条件）

## 背景

原 INST1-AC06 要求在不同 Windows 身份、不同 WSL machine-id 和空数据根上独立复现，保证等级最高，但项目所有者只有一台电脑，无法提供第二台物理机。继续把它作为 V1 必需门会让已经具备本地部署能力的私人单机产品永久停留在外部资源阻断状态。

## 备选方案

| 方案 | 保证强度 | 成本 | 决策 |
|---|---|---:|---|
| A. 独立 Windows/WSL 机器 | 可覆盖不同身份、内核、驱动和硬件组合 | 需要另一台机器或干净 VM、重新复制约数十 GB 工件 | 保留为增强验收 |
| B. 同机隔离可移植性 | 覆盖新数据根、隔离 venv、离线 wheelhouse、便携制品、参数化路径和真实生命周期 | 不新增硬件，复用现有离线制品 | **V1 采用** |
| C. 只做源码白盒检查 | 只能证明脚本看似可配置 | 低，但无法证明依赖和生命周期 | 拒绝 |

## 决策

V1 将 INST1-AC07 作为最低部署门。报告必须绑定当前 Git revision 与发布冻结，并同时证明：

1. Core/Avatar 均在 Python 3.12、`include-system-site-packages=false` 的全新隔离 venv 中通过依赖和源码导入；
2. Core/Avatar wheelhouse 已逐文件复算 SHA-256，并以 `--no-index` 安装；
3. 安装器曾在 `/tmp` 下的替代 WSL home/data root 完成 prepare，运行路径均可参数化；
4. 本地模型、CosyVoice 源码、授权音色和 Avatar 由脱敏制品报告验证，生产前端为 Git 跟踪工件；
5. 当前目标机真实执行 start×2、status、Avatar recover、stop×2，最后 PID 与端口归零；
6. 报告固定写明 `same_windows_identity`、`same_wsl_machine_id`、`same_gpu_driver_stack` 三项限制。

INST1-AC06 保留且仍可替代 AC07 提供更高保证；两个 schema 与最终总门策略显式分离，禁止把 AC07 表述为“干净机通过”。

## 影响

- 用户可以只用一台电脑完成个人/研究用途 V1 验收。
- 不新增运行时服务，不改变模型、端口、数据格式或日常启动路径；迁移成本仅为验收脚本和文档。
- V1 的可移植性结论限定为“同平台、同架构、满足文档前置条件时具备重建能力”。Windows/WSL/GPU 驱动跨机器兼容仍未知。
- 商业用途仍受 Wav2Lip ResearchOnly 限制，与本决策无关。

## 回滚

最终聚合器保留 `clean-machine` 策略。获得第二台机器后运行 INST1-AC06，并以 `-DeploymentPolicy clean-machine` 重签，无需修改产品代码或数据。
