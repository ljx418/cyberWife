# INST1 验收标准

| ID | 场景 | 出门门槛 |
|---|---|---|
| INST1-AC01 | 新Windows用户路径 | 生产代码/Launcher无`Administrator`硬编码 |
| INST1-AC02 | audit | 缺少项逐项返回机器可读失败；不写系统状态 |
| INST1-AC03 | prepare | 仅创建项目私有目录/缺失配置；重复运行幂等；已有文件不覆盖 |
| INST1-AC04 | verify | 四组件工件、venv、模型与前端均完整才返回0 |
| INST1-AC05 | 生命周期 | 新生成配置下start/status/recover/stop通过 |
| INST1-AC06 | 干净环境 | 全新Windows 11用户+干净WSL从工件准备到一键启动独立复现 |

AC01～05可在目标机/隔离目录验证；AC06必须有新的系统环境证据。
