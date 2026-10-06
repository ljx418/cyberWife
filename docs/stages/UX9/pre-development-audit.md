# UX9 开发前审计

**结论**：开放Critical/Major=0，可以进入实现。

| 风险 | 等级 | 闭环方式 | 状态 |
|---|---|---|---|
| 用“回复非空”冒充可交流 | Critical | 强制逐场景语义规则、事实答案和上下文追问门 | CLOSED FOR ENTRY |
| 用文字正确冒充音频可懂 | Critical | 拼接真实输出PCM并由独立SpeechRuntime重新识读，计算CER | CLOSED FOR ENTRY |
| 同一TTS生成输入造成循环偏好 | Major | 输入ASR与输出ASR分开计分；事实/语义门直接检查LLM文字；报告披露同模型音色限制 | CLOSED FOR ENTRY |
| 提高门槛导致真正插话变慢 | Major | 播放态持续门固定240ms，保留既有400ms取消门并回归按钮打断 | CLOSED FOR ENTRY |
| 噪声种类无法仅凭RMS区分 | Major | 本轮先关闭已复现的低幅/瞬态误触；持续高能类人噪声列为残余风险，不宣称通用声纹识别 | CLOSED FOR ENTRY |
| 验收落盘用户音色或对话 | Critical | 音频全程内存处理，报告仅保留合成脚本、转写、哈希和指标 | CLOSED FOR ENTRY |
| 为质量同时常驻第二套模型 | Major | 复用现有SpeechRuntime、Gateway和串行GPU调度 | CLOSED FOR ENTRY |

本阶段不改变V1离线、隐私、资源、首响≤7秒、打断取消和Avatar协议。若真实闭环暴露模型级不可控语义失败，再提交技术路线而不以降低正确性门槛放行。
