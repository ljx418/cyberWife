# UX8 验收结果：普通话转写与自然停顿连续性

**日期**：2026-10-06
**结论**：机器门 PASS；物理麦克风主观复验 PENDING。

## 已实现

- Faster-Whisper 保持 `language=zh`、`beam_size=1` 与单轮独立解码，增加短普通话热词，不增加模型和常驻内存。
- `MandarinTranscriptNormalizer` 先繁转简，再只替换粤语特有词形；普通话歧义字不进入替换表。
- 全文字幕与带时间戳 segments 使用同一归一逻辑；中文字符间的模型空格被清理，拉丁词两侧空格保留。
- Chrome 输入端点静音 hangover 从 30 帧/600ms 调整为 45 帧/900ms；20ms PCM、200ms preroll、60ms onset 和后端 30 秒上限不变。
- 非缓存回复继续等待完整短句并只进行一次 CosyVoice 推理。

## 真实模型证据

- 三条既有授权 PCM 由当前 Faster-Whisper CUDA/FP16 实际转写，3/3 语义正确，无异常符号；耗时分别约 318ms、101ms、106ms。
- 当前四进程真实栈执行 3 轮授权 PCM：3/3 完成，event_seq 严格递增，generation 分离，无 error/media degradation；字幕三轮均为“今天天气不错我想和你聊聊天”，Avatar 累计 838 帧。
- 该 E2E 的 10～11 秒是直到整条音频与 Avatar 处理完成的总轮时长，不是首响；本轮没有用它冒充 PRD 首响数据。
- 原始机器结果位于忽略目录 `audit/v1/UX8/`，不包含物理麦克风录音。

## 自动化回归

- Backend：361 passed，5 skipped。
- 根测试：31 passed。
- Avatar：13 passed。
- Frontend：生产构建 PASS，Playwright 16 passed，验收核心 3 passed。
- 生命周期：真实栈启动四组件全健康；验证后四组件 PID 和端口全部清零。

## 阶段门

| 门 | 状态 | 说明 |
|---|---|---|
| UX8-AC01～02 | PASS | 普通话归一与不越界用例通过 |
| UX8-AC03 | PASS | 44 个静音帧保持同轮，第 45 帧只结束一次 |
| UX8-AC04 | PASS | 真实模型 3/3，无字符污染，均 <2s |
| UX8-AC05～06 | PASS | 单次整句 TTS 与全量回归通过 |
| UX8-AC07 | PENDING | 需用户重启后用物理麦克风确认实际口音、停顿和听感 |
