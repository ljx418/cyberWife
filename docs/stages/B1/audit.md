# B1 实施前审计

**日期**：2026-09-24  
**结论**：PASS，可开始B1实质开发。

- PRD覆盖：FR-07、FR-08、FR-15及NFR-03/04/09；未提前承诺B2音频或B3打断。
- 架构：保持模块化单体Gateway + 独立SpeechRuntime + Windows llama.cpp；没有引入云端、Docker或新数据库。
- 资源：原28GB WSL门禁已由用户批准的V1.3预算取代。B1不加载TTS/Embedding，ASR与后续TTS保持分时边界。
- 防虚假验收：mock只验证合同；阶段PASS必须包含20轮真实授权音频、真实ASR、真实LLM和目标机资源证据。
- 隐私：PCM仅内存传输；真实文本只在业务数据库按recording policy存储，结构化日志只记录长度/哈希/耗时。
- 安全：loopback、帧硬上限、有界缓冲、拒绝乱序/跨轮；不接受客户端提供任意路径或模型参数。
- 截止时间与失败：ASR/LLM分别硬超时，超时进入error/listening恢复路径；不得无限占用队列或event loop。
- 未关闭致命/重大意见：0。

## 实施中问题闭环

- `B1-P1-01`：旧emoji正则范围跨越CJK，真实中文回复被全部删除并进入error。已改为明确emoji区段，增加中文保留测试；CLOSED。
- `B1-P1-02`：首轮真实LLM暴露`<think>`且逐token发送。Prompt加入`/no_think`与40汉字约束，Sanitizer屏蔽闭合/未闭合推理块，delta按句/长度合并；20轮泄漏0；CLOSED。
- `B1-P1-03`：Gateway启动日志打印私有资产绝对路径。已移除并重启覆盖日志，敏感搜索0命中；CLOSED。
- `B1-P1-04`：旧内存口径把llama GGUF mmap working set与RSS相加，夸大不可回收占用。合同改为Windows private bytes + WSL RSS硬门，并用宿主Available/WSL MemAvailable兜底；实测9.56GiB、两侧余量≥2GB、swap=0；CLOSED。
- `B1-P1-05`：授权音频`user_clip_v2.wav`历史逐字稿错误。四种派生格式真实ASR均确认正确文本是“早上好，宝贝，快起床了，起来陪我玩”；已修B0/Cosy复测入口并使旧Cosy CER结论失效。B2必须公平重测；B1问题CLOSED，B2前置项已明确。

## 出门审计

- 真实E2E：20/20；事件序号、turn和trace归属正确。
- 自动回归：B1定向71项PASS；最终全量242 PASS / 4 SKIP，前端Vite构建PASS。4个skip仅因WSL未发现无扩展名`pwsh/powershell`，真实`powershell.exe`三轮生命周期已在B0覆盖。
- 回归修复：旧LLM测试硬编码8090“必定关闭”，与目标机真实服务并行运行冲突；已改用动态未监听端口后全绿。
- PRD检视：B1范围PASS，未用文本链冒充B2首响或V1总验收。
- 未关闭P0/P1：0。
- 结论：**B1 PASS，可制定并审计B2计划。**
