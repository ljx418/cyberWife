# B0 详细开发计划：可运行基线与合同修复

## 目标

交付真实、幂等、可恢复的一键生命周期；健康页只显示功能探针事实，不能按文件存在或旧清单推断 ready。

## 实施项

1. RuntimeLauncher 修复 Gateway 参数、llama `/health`、组件端口和项目 PID 所有权；禁止杀非项目进程。
2. Gateway 支持 TOML 运行配置并统一 ext4 数据根、数据库、资产和日志路径。
3. ModelRegistry 区分 manifest 状态与 runtime probe；只有实际 probe 成功才 ready。
4. HealthAggregator 采集 RAM、磁盘、GPU 数据并暴露探针时间、错误与降级状态。
5. 建立可复用 functional probe runner；损坏 fixture 和不可达服务必须显示 degraded/error。
6. 对 llama Windows 薄启动器及配套 DLL 执行版本、哈希、`/health` 和 completion 探针；仅在功能失败时用官方发布包替换。
7. 建立 B0 单元、合同、PowerShell、进程生命周期与目标机证据脚本。

## 不在 B0

不实现完整 WS TurnPipeline、TTS 播放、Avatar WebRTC、记忆业务或视觉重构；这些分别属于 B1～B4。
