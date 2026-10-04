# B0 完成后 PRD 规格检视

**日期**：2026-09-24  
**结论**：PASS；用户批准按32GB整机、约16GB可用预算开发，资源门槛已纠正且无规格漂移或虚假验收。

| 规格 | 本阶段证据 | 判断 |
|---|---|---|
| FR-03 六组件与资源真实状态 | 六组件实时 functional probe；聚合资源来自系统/NVIDIA | PASS |
| FR-15 一键启动/停止/恢复 | 三轮真实四服务生命周期及故障注入 | PASS |
| FR-17 本地模型与授权资产 | LLM/ASR/VAD/TTS/Embedding/Avatar 均真实加载；TTS 使用授权参考音频 | PASS |
| FR-18 本地私有运行 | loopback、无公共 STUN、Avatar external TTS/local LLM | PASS |
| NFR-03 可恢复性 | 单组件 recover、幂等 stop/start、失败回滚 | PASS |
| NFR-04 隐私 | 无云端 provider、停止后临时音频为零 | PASS（B0 范围） |
| NFR-09 可观测性 | probe 时间、错误、device、dtype、资源可观测 | PASS |
| NFR-10 可维护性 | 配置合并、专用运行环境、受管 PID 所有权 | PASS |
| NFR-02 资源门槛 | 当前WSL 15.52GiB；短时组合总用量8.86GB；新合同为项目峰值≤14GB并保留约2GB余量 | PASS（B0）；B2/B3继续峰值/稳态验收 |

B0 没有声称完成实时会话、打断、记忆、1小时稳态或CosyVoice对比；这些仍属于B1～B5，避免把组件smoke冒充V1端到端验收。B0门禁已关闭，可按计划开始B1。
