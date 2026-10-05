# INST1-AC06R 阶段结果

**结论**：AUTOMATION PASS / CLEAN ENVIRONMENT RUN PENDING

AC06初版执行器在外部审查前的深层白盒复核中暴露三项真实阻断：新数据根没有默认Avatar、Gateway依赖Git忽略的开发机音频、模型注册表包含开发机绝对路径。阶段被打回开发，而非以当前机负例冒充完成。

本轮已交付：

- `config/local-artifacts.example.json`：不带真实路径/授权的清单模板。
- `ops/acceptance/prepare_local_artifacts.py`：七个实时模型（含TTS回退）的纯离线验证、私有发布、注册表生成与发布复核；重复准备保留既有核验元数据。
- 安装器/AC06执行器：绑定清单SHA，验证五项干净前置，自动导入模型、Cosy源码、授权音色和Avatar。
- Gateway/RuntimeLauncher：bootstrap参考音频与Avatar恢复；旧仓库私有音频硬编码已删除。
- 当前开发机：依据已有同意记录做私有迁移，真实启动四组件、Avatar恢复、双停和端口归零通过。

自动化证据：后端358 passed/5 skipped；根27 passed；Avatar13 passed；前端生产构建与Playwright15 passed；V1FINAL核心3 passed；PowerShell AST与XML/差异检查通过。

唯一未完成项仍是外部事实：需要新的Windows SID、新WSL machine-id、初始无数据根/venv/runtime config/本机注册表的环境，使用离线wheelhouse和私有制品清单执行正式accept。
