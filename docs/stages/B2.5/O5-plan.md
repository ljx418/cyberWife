# B2.5-O5 严格问候预热开发计划

**日期**：2026-09-25  
**状态**：开发前冻结

## 目标与最小实现

- 默认只启用完整句“你好”，复用Gateway现有TTS启动预热产生的PCM，不增加`interactive_ready`等待。
- 允许策略白名单覆盖：`你好/嗨/早上好/晚上好/你在吗/能听见吗/谢谢/再见`，一次实际配置最多6项；本批次不实现模糊或语义匹配。
- 规范化仅去首尾空白、全部内部空白和句末标点；带前后附加语义、天气、记忆、“继续说”均不命中。
- 缓存键包含`persona_version/voice_version/llm_revision/tts_revision/policy_version/text`；任一变化即未命中。
- 缓存仅进程内保存回复文字和PCM帧，总字节≤64MiB；不写SQLite、日志或备份。
- 命中旁路LLM/TTS，但仍经过既有状态机、Avatar、WebSocket、浏览器首非静音确认与`cache-hit`指标桶。

## 实施顺序

1. 新增纯领域`WarmResponsePolicy/Context/Key/Entry`和单元测试。
2. 新增线程安全有界`WarmResponseCache`，超限拒绝写入并支持整体失效。
3. 扩展`TurnPipeline`命中分支和`MediaPipeline.stream_cached`，保持generation/状态/播放合同。
4. composition root复用现有“你好。”预热帧构建默认条目；不新增后台模型任务。
5. 跑正例、负例、版本失效、64MiB、正常链不等待和浏览器真实命中测试。

## 停线条件

- 天气、记忆、继续说、前缀/后缀附加语义任一错误命中；
- 命中数据进入normal桶，或未命中被标记cache-hit；
- 版本变化仍命中、缓存写盘、超过64MiB、旧generation复播；
- 命中路径绕过Avatar/浏览器确认，或普通路径P95/资源发生回退。
