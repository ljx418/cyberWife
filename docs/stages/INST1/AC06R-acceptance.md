# INST1-AC06R 验收标准

## 自动化出门条件

1. 缺少必需模型、授权声明、参考音频、Avatar 结构或声明 SHA 不符时，准备器必须失败且不发布半成品。
2. 合法清单在临时目录中生成七个 V1 实时模型（含TTS回退）的本机注册项、私有 bootstrap 清单、参考音频和 Avatar；升级既有环境时不得把verified元数据降级；生成物不得包含开发用户名。
3. Gateway 源码不得再含 `assets/voice/user_clip_v2.wav`，且 bootstrap 参考音频存在性/边界经过测试。
4. RuntimeLauncher 数据库无激活 Avatar 时从 `$DataRootWsl/bootstrap/avatar-id` 恢复；非法 ID 必须拒绝。
5. 安装器 `verify` 必须检查本机注册表、bootstrap 清单、音频、Avatar 和全部模型路径。
6. AC06 必须使用 `-ArtifactManifestWsl`，报告绑定清单 SHA-256，且仍只使用离线 wheelhouse。
7. 后端、根目录、Avatar、前端和验收工具回归全绿；仓库不跟踪私人媒体或 `model-registry.local.yaml`。

## 外部实机出门条件

在非开发 Windows SID、非开发 WSL machine-id、初始无 `~/.cyberWife` 和 `runtime.local.toml` 的环境运行 AC06：安装准备/复核、启动两次、状态、Avatar 定向恢复、停止两次全部通过，最终端口关闭。该项不能在当前开发身份上自证。
