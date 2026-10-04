# INST1 预开发审计

| 风险 | 严重度 | 闭环 | 状态 |
|---|---:|---|---|
| 覆盖正式配置/数据 | Critical | prepare只创建缺失项，存在即拒绝覆盖 | CLOSED FOR ENTRY |
| 安装器静默联网/改防火墙 | Critical | 只校验本地工件；白盒扫描禁止网络安装命令 | CLOSED FOR ENTRY |
| 当前机verify冒充干净机 | Major | AC06单列外部环境门 | CLOSED FOR ENTRY |
| 用户名硬编码复发 | Major | 生产路径静态测试 | CLOSED FOR ENTRY |
| prepare未安装依赖 | Major | INST1.1增加隔离venv、锁文件、离线/显式联网两路径及import验证 | CLOSED FOR ENTRY |
| Speech继承系统Python漂移 | Major | 启动器强制受控`SpeechPythonWsl`，preflight检查可执行 | CLOSED FOR ENTRY |
| HTTP 200被误判为功能ready | Major | 启动器同时解析JSON状态；Speech只在VAD/ASR/Embedding真实预热后返回ready，TTS探针不作为Speech进程就绪条件 | CLOSED FOR ENTRY |
| WSL调用Windows启动器时`/init` relay等待长期子进程 | Minor/验收工具 | Windows `powershell.exe`实际已退出，用户双击`.cmd`不经该relay；WSL自动化按UX4已实现逻辑在功能ready后只回收relay | CLOSED |

开放Critical/Major审计意见=0，允许进入INST1.1实现；AC06在缺少新环境时保持阻断。
