# UX5 实施后审计

**日期**：2026-10-05

**结论**：代码、合同和自动证据一致；无新增Critical，人工感知门仍开放。

| 审计项 | 结果 | 说明 |
|---|---|---|
| PRD FR-10 | CONDITIONAL | 时钟、错位、动态、FPS已量化；自然度人审待完成 |
| NFR-01 | PASS BY DESIGN | 新增295ms计入首响，既有7s硬门仍有裕量；B5需组合回归 |
| NFR-02 | PASS | batch4真实infer/final FPS均过门，未增加常驻模型 |
| NFR-04 | PASS | 外部工具下载在私有cache且不参与产品运行；验收媒体不入Git |
| B3打断 | PASS REGRESSION | 预缓冲音源仍登记到generation集合，cancel立即stop；浏览器合同测试通过 |
| 架构语义 | PASS | Gateway PCM仍是唯一音频；Avatar只产视频；前端仅增加首源排程 |
| 虚假验收风险 | CLOSED | 公共SyncNet低置信度明确标INCONCLUSIVE；未伪装成论文LSE |
| 许可证 | OPEN RELEASE BLOCK | Wav2Lip ResearchOnly仍阻断商业发布 |

## 回退

- 把启动器batch恢复8并把`AVATAR_AUDIO_PREROLL_SECONDS`恢复0即可回到旧行为；无需迁移数据或重建Avatar。
- 若人工认为声音明显晚于嘴型，先在280～310ms内用同一工具复测，不修改内容对齐或FPS门。
- 若人工认为口型形状不自然，不能只改延迟；应进入模型/融合路线比较。
