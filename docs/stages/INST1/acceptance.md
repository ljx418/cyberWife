# INST1 验收标准

| ID | 场景 | 出门门槛 |
|---|---|---|
| INST1-AC01 | 新Windows用户路径 | 生产代码/Launcher无`Administrator`硬编码 |
| INST1-AC02 | audit | 缺少项逐项返回机器可读失败；不写系统状态 |
| INST1-AC03 | prepare | 仅创建项目私有目录/缺失配置；重复运行幂等；已有文件不覆盖 |
| INST1-AC04 | verify | 四组件工件、venv、模型与前端均完整才返回0 |
| INST1-AC05 | 生命周期 | 新生成配置下start/status/recover/stop通过 |
| INST1-AC06 | 干净环境 | 全新Windows 11用户+干净WSL从工件准备到一键启动独立复现 |
| INST1-AC07 | 依赖准备 | 离线wheelhouse可复现；联网安装需双重显式开关；隔离venv的`pip check`与关键import全通过 |
| INST1-AC08 | Speech解释器 | 生产启动命令使用受控venv，无系统`python3`逃逸；四组件生命周期回归通过 |
| INST1-AC09 | 功能健康 | 端口HTTP 200且JSON状态符合各组件ready集合才签就绪；Speech在VAD/ASR/Embedding预热完成前必须为loading |
| INST1-AC10 | 全新隔离venv | Core/Avatar均不继承system packages；真实安装完成；`pip check`=0冲突；关键import与项目源码加载PASS |

AC01～05可在目标机/隔离目录验证；AC06必须有新的系统环境证据。
