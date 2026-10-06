# INST1-AC07 实施后内部审计

**结论**：代码与合同完成；真实Windows生命周期报告PENDING。

| 审查项 | 结果 | 证据 |
|---|---|---|
| 保证等级不混淆 | PASS | AC07使用独立gate/schema；AC06报告不能通过AC07策略测试 |
| 隔离/离线证据 | PASS | 构建器逐项复核10个venv检查、8个离线安装检查、`/tmp`替代数据根和wheelhouse全量SHA |
| 便携工件 | PASS | 实际复核261个wheelhouse文件全部SHA；当前active avatar/音色/七模型路径/CosyVoice发布结构验证PASS；前端受Git跟踪且部署路径参数化 |
| 生命周期 | IMPLEMENTED | Windows入口要求start×2/status/recover/stop×2与最终端口/PID归零 |
| 失败关闭 | PASS | 缺字段、限制、步骤、哈希、revision或策略不匹配均FAIL；缺报告PENDING |
| 隐私 | PASS | 报告只存哈希、布尔、步骤名和限制，不存操作者/绝对路径/音频/对话 |

当前受限终端的`WSL_INTEROP` socket不存在，任何`powershell.exe`/`cmd.exe`调用都在进入脚本前报`UtilBindVsockAnyPort`；因此未伪造PowerShell AST或生命周期PASS。Linux侧总门专项8/8、根测试36/36、Avatar非端口11/11、前端build与现场核心1/1通过；261文件wheelhouse与本地制品真实验证PASS。端口型Avatar用例和Playwright webServer因当前sandbox禁止loopback socket未执行成功；`.git`在本会话只读，因此最终提交/release重签亦保持PENDING。
