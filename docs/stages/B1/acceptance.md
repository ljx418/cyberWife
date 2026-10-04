# B1 验收标准

1. WebSocket仅接受合法JSON控制帧或646字节二进制帧（uint32 turn_id + uint16 chunk_seq + 640字节PCM）；>4KB、尺寸错误、乱序、跨轮均可观察地拒绝。
2. 每连接音频缓冲≤30秒且queue有界；输入停止后queue depth回到0；推理不阻塞event loop健康请求。
3. Silero VAD真实检查语音；无语音不创建turn。Faster-Whisper返回final文字、置信度、语言及segment时间戳。
4. 只有`transcript.final`创建turn；同一capture重复final不得产生第二turn。
5. 合法事件顺序为listening→thinking→speaking→listening；非法状态转换、event_seq倒退、旧turn文本串入新turn均为0。
6. PromptCompiler使用真实profile；LLM通过本机llama.cpp流式生成；最终文本经OutputSanitizer，增量与final归属同一session/turn/trace。
7. 授权真实音频固定语料连续20轮，至少19轮产生非空且归属正确的final字幕与回答；不得用mock作为E2E证据。
8. 日志可按trace定位阶段/耗时/错误，但不包含原始PCM、完整prompt、完整逐字稿或完整回复正文。
9. B1组合运行Windows项目private bytes + WSL项目RSS≤14GB，宿主/WSL可用内存均≥2GB、无持续swap-in/OOM；停止后临时音频增量=0。
10. 全量自动测试和前端构建通过；任何真实模型跳过单列，不能计为PASS。

## 2026-09-25 执行结果

| 条目 | 结果 | 证据 |
|---|---|---|
| 1 帧合同/乱序/跨轮 | PASS | 合同测试 + WebSocket真实帧 |
| 2 有界缓冲/非阻塞/回落 | PASS | 30秒硬上限；queue capacity=32；每轮depth=0 |
| 3 真实VAD/ASR/时间戳 | PASS | CUDA FP16 ASR；20轮已知文本100%；授权样本保留segment |
| 4 final唯一建turn | PASS | 单元/WS/20轮证据 |
| 5 状态/序号/归属 | PASS | event_seq严格递增；跨轮0；非法转换0 |
| 6 profile/LLM/sanitize | PASS | 真实Qwen3-14B；`/no_think`；推理泄漏0 |
| 7 20轮真实链 | PASS | 20/20，超过19/20门槛 |
| 8 日志隐私 | PASS | 敏感字符串搜索0命中 |
| 9 资源/临时音频 | PASS | 非可回收约9.56GiB；宿主/WSL≥2GB；swap=0；临时音频0 |
| 10 回归 | PASS | 全量测试与构建结果见审计 |

阶段总判定：**PASS**。
