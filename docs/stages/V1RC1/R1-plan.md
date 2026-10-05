# V1RC1-R1 修复计划：当前人物恢复与整句首响

**触发证据**：RC1-AC02 首轮功能 20/20，但 runner 因 Avatar 心跳版本覆盖视频协议版本而汇总 FAIL；运行指标正常链首响 P95=8791.107ms，超过 7 秒。

## 根因与动作

1. `accept_turns.py` 未像真实前端一样把持久化 active avatar id 带入 WebSocket，并把 `avatar.heartbeat version=1` 错记为视频协议版本。修正 runner，使其验证当前 active Crop V2、仅从 `video.config` 读取协议。
2. `RuntimeLauncher.ps1` 默认固定旧 avatar id。启动时若调用者未显式覆盖，则从私有数据库读取已授权 active derivative；空库/异常时才回退内置人物。
3. 当前 LLM 合同允许两句/40汉字，UX7 又等待完整回复后才启动单次 TTS，尾延迟相加。将日常回复约束为一条自然短句、最多18汉字，并把正常生成上限由96降至48 token；仍保留完整句一次合成。
4. 不以截断成残句或恢复碎片化 TTS 换取指标；真实回复若仍超门，再分析 LLM/TTS运行态而不是继续降低体验。

## 验收

- Prompt 合同测试明确“一句话、18汉字”；TurnPipeline 生成参数上限48。
- 启动器测试覆盖数据库 active id、显式覆盖、空库回退。
- 真实 20 轮全部使用 active Crop V2，协议v2，功能成功率≥95%。
- 真实运行指标首响 P95≤7秒；随后才恢复 RC1-AC03/04/05。
