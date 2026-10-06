# INST1-AC07 实施后内部审计

**结论**：PASS；代码、合同和真实Windows生命周期证据闭环。

| 审查项 | 结果 | 证据 |
|---|---|---|
| 保证等级不混淆 | PASS | AC07使用独立gate/schema；AC06报告不能通过AC07策略测试 |
| 隔离/离线证据 | PASS | 构建器逐项复核10个venv检查、8个离线安装检查、`/tmp`替代数据根和wheelhouse全量SHA |
| 便携工件 | PASS | 实际复核261个wheelhouse文件全部SHA；当前active avatar/音色/七模型路径/CosyVoice发布结构验证PASS；前端受Git跟踪且部署路径参数化 |
| 生命周期 | PASS | Windows入口实跑start×2/status/recover/stop×2；Avatar PID真实变化；最终端口/PID归零 |
| 失败关闭 | PASS | 缺字段、限制、步骤、哈希、revision或策略不匹配均FAIL；缺报告PENDING |
| 隐私 | PASS | 报告只存哈希、布尔、步骤名和限制，不存操作者/绝对路径/音频/对话 |

本轮在可写Git、可用Windows互操作和可绑定loopback的宿主上执行。全量回归为Backend 361 passed/7 skipped、根工具37 passed、Avatar 13 passed、Playwright 16 passed、现场核心3 passed、前端build PASS、PowerShell AST 4文件PASS。261文件wheelhouse与本地制品真实验证PASS。AC07首次实跑暴露历史端口竞态并完成受管清理；随后暴露嵌套PowerShell管道等待和PowerShell 5路径转义，两项均修复、加测试并从零重跑。最终报告12/12步骤PASS且服务归零，没有把中间失败改写为首跑成功。
