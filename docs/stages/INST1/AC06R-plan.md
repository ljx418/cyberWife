# INST1-AC06R 可移植离线制品修复计划

## 目标

修复 AC06 干净机器验收暴露的三个阻断：模型注册表依赖开发机绝对路径、Gateway 依赖仓库外私人音频、Avatar 默认数据未随安装建立。修复后，干净 Windows 用户与干净 WSL 数据目录可以仅凭仓库、离线 wheelhouse 和一个经授权的本地制品清单完成安装与启动。

## 实现范围

1. 定义 `cyberwife-local-artifacts` JSON 清单，显式绑定 V1 七个实时模型（含Qwen3-TTS回退）、CosyVoice 源码、参考音频及预构建 Avatar。
2. 新增纯离线制品准备器：验证文件类型、授权声明、Avatar 结构和可选 SHA-256；生成 Git-ignore 的 `model-registry.local.yaml`；将参考音频与 Avatar 复制到用户私有数据根；输出不含原文和绝对私有路径的审计报告。
3. 安装器在 `prepare/verify` 阶段调用并复核该准备器，运行时配置只引用用户数据根中的 bootstrap 清单。
4. Gateway 从 bootstrap 清单读取缺省参考音频和提示文本，不再访问仓库 `assets/voice/user_clip_v2.wav`；已激活且有同意记录的用户音色仍然优先。
5. RuntimeLauncher 在数据库无已激活 Avatar 时读取 bootstrap Avatar ID，不再假定一个不存在的数据集。
6. AC06 干净机脚本只接受制品清单驱动，保留离线、身份隔离、幂等启停与清理证据。

## 非目标

- 不分发模型、用户照片、用户音频或第三方权重。
- 不联网下载制品。
- 不降低 TTS/Avatar 的功能探针或 V1 硬件上限。

## 实施顺序

合同测试失败 → 制品准备器 → 安装器/启动器/Gateway 接线 → 单元与 PowerShell 语法测试 → 全量自动化回归 → 文档与 drawio 同步 → 独立干净环境实测。
