# INST1-AC07 验收标准

| ID | 用户场景/操作 | 出门门槛 |
|---|---|---|
| AC07-01 | 在当前提交运行 AC07 | 工作树跟踪文件干净；revision 与 release_id 绑定 |
| AC07-02 | 从离线包重建 Python 环境 | 两个全新 Python 3.12 venv 隔离；10/10 导入与 pip check 通过 |
| AC07-03 | 不联网安装依赖 | wheelhouse 全量 SHA 匹配；Core/Avatar 均以 `--no-index` 安装 |
| AC07-04 | 把运行数据放到另一空目录 | `/tmp` 替代 home/data root prepare 通过；安装和启动路径可参数化 |
| AC07-05 | 搬运本地运行工件 | 模型、CosyVoice、音色、Avatar 脱敏制品报告 PASS；前端是 Git 跟踪工件 |
| AC07-06 | 一键启动、恢复、停止 | start×2/status/recover-avatar/stop×2 全 PASS，最后端口/PID 归零 |
| AC07-07 | 阅读保证范围 | 报告明确同 Windows 身份、同 WSL machine-id、同 GPU 驱动均未交叉验证 |
| AC07-08 | 最终总门 | `single-machine-portability` 策略只接受 AC07 schema；字段/哈希/revision 错误立即 FAIL |

AC07 通过只证明“满足同平台前置条件时具备一定可移植性”，不得宣传为独立机器或跨驱动兼容性通过。
