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
| 新WSL缺失`ensurepip/python3-venv` | Major | 隔离实测已复现；创建器按标准`venv`、`uv`、`virtualenv`顺序尝试，均不可用时输出明确的`python3.12-venv`前置错误，不自动sudo/apt | CLOSED FOR ENTRY |
| `uv venv`默认无pip且选到托管Python 3.11 | Major | 必须解析并传入系统Python绝对路径，使用`--seed`；已有venv也必须通过Python 3.12+pip自检，否则清理重建 | CLOSED FOR ENTRY |
| Diffusers 0.40与Cosy Transformers 4.51的HF Hub约束冲突 | Major | Core与Avatar回到Cosy官方兼容线`diffusers 0.29.0`，显式锁定`huggingface-hub 0.36.2`；以干净venv解析和`pip check`为准 | CLOSED FOR ENTRY |
| 两套环境共用平铺wheelhouse造成版本漂移 | Major | 固定`core/`、`avatar/`分仓；安装器按组件选择；分别解析和验收 | CLOSED FOR ENTRY |
| 离线包被截断或替换 | Major | 构建后生成相对路径SHA256清单；安装前验证，任何缺失/额外/摘要不符均失败 | CLOSED FOR ENTRY |
| “离线安装”仍访问索引 | Critical | 安装命令必须包含`--no-index`，验收使用隔离venv并白盒记录pip命令；不得用已有生产包代替 | CLOSED FOR ENTRY |
| wheelhouse挤占C盘或写入Git | Major | 默认位于WSL `$HOME/.cyberWife/wheelhouse`，Git只保存工具与脱敏证据，不保存wheel二进制 | CLOSED FOR ENTRY |

开放Critical/Major审计意见=0，INST1.1～INST1.3均已按计划进入实现与真实验收；AC06在缺少新环境时保持阻断。
