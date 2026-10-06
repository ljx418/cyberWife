# UX9 实现审计

**日期**：2026-10-06
**结论**：Critical/Major开放项=0；允许签署自动化阶段门。

## 根因与闭环

| 根因 | 实现闭环 | 白盒证据 |
|---|---|---|
| 播放态与监听态共用低RMS、60ms起声门，环境噪声易误打断 | 普通监听改为RMS 0.018/100ms；播放态改为RMS 0.035/240ms；保留900ms停顿 | `prototype/src/services/InputAudioSession.ts`、Playwright播放态噪声/脉冲/持续人声用例 |
| 主链未向`PromptCompiler`传入历史，追问无法可靠衔接 | 每会话保留最近三组问答；结束/删除/进程关闭立即清除；no-record不落盘 | `TurnPipeline._recent_history`、`forget_session`及双轮单测 |
| 本机bootstrap参考音频与逐字稿不匹配，CosyVoice泄漏错误prompt | 启动和每个新音色版本都用真实SpeechRuntime回读，CER>15%拒绝；本机manifest修正为真实逐字稿 | `voice_reference_quality.py`及6项单元测试；Gateway启动成功即证明当前pair通过 |
| CosyVoice流式路径首音不稳，随机采样导致相同文本偶发串音 | V1默认整句生成；seed固定；实测短文本≤7字使用seed+1，其余使用基准seed；环境变量保留可逆开关 | `CosyVoiceTtsAdapter`、适配器合同测试、三轮真实A/B记录 |
| LLM回复可随机漂移、过长或只有一个字 | 温度0、24 token；优先准确回答和最近上下文；一句7～14字、常见易听清用词 | `PromptCompiler`、`TurnPipeline`及真实六场景报告 |
| 既有E2E只断言回复非空 | 新增CosyVoice合成输入→真实ASR→Qwen→CosyVoice→真实ASR闭环；分别判输入、语义、输出和时延 | `tests/ux9/accept_voice_dialogue.py`、`audit/v1/UX9/final.json` |

## 风险复核

- 没有新增常驻模型；复用现有SpeechRuntime作启动期参考音色校验，运行稳态资源边界不变。
- 真实音频只在内存中流转；报告只保存合成脚本、转写、指标和SHA256。
- 短文本seed分支是当前授权音色与CosyVoice2的实测策略，不外推为所有音色通用结论；新音色仍必须经过参考逐字稿门和人工试听。
- 持续高能、类人环境声仍可能满足240ms插话门；V1没有声纹级说话人确认，不宣称能过滤所有电视人声。
- 本轮不改变generation、取消协议或Avatar队列；既有打断P95≤400ms证据继续有效。

## 审计结论

实现与UX9计划、PRD离线/隐私/首响/打断约束一致。未发现新增致命或重大规格偏差；自动化证据可以进入PRD检视，物理麦克风与主观自然度仍由V1人工总验收签署。
