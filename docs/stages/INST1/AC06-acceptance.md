# INST1-AC06 干净环境验收标准

> 历史标准：已由`AC06R-acceptance.md`补强；正式验收必须同时满足AC06R。

| ID | 场景 | 门槛 |
|---|---|---|
| AC06-01 | 当前开发环境误运行 | Windows SID哈希或WSL machine-id哈希命中拒绝值时，在任何写入前失败 |
| AC06-02 | 非干净环境误运行 | 数据根、受控venv或runtime.local.toml预先存在时失败 |
| AC06-03 | 离线依赖准备 | wheelhouse清单校验；Core/Avatar隔离venv仅`--no-index`安装；pip check与关键import通过 |
| AC06-04 | 本地工件 | LLM、ASR、TTS、Avatar、Embedding、ComfyUI工作流/模型及Cosy源码全部由本地工件满足；报告绑定workspace revision、wheelhouse manifest SHA256和CosyVoice revision |
| AC06-05 | 一键生命周期 | start×2均保持单实例且健康；status全健康；Avatar recover后全健康；stop×2成功并归零 |
| AC06-06 | 失败清理 | 任一步失败均尝试受管stop，不杀外部PID，不删除模型/用户数据 |
| AC06-07 | 报告隐私 | 只含身份哈希与状态；不含用户名、SID/machine-id原文、绝对私有路径、日志正文或模型内容 |

只有新环境报告`result=PASS`且退出码0才能关闭INST1-AC06。当前机的`fingerprint`或负例只能证明防冒签合同。
