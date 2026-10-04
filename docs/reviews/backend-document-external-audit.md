# cyberWife V1 后端外部文档审查

**日期**：2026-09-24  
**执行器**：Claude Code CLI，只读 `plan` 权限  
**结论**：CONDITIONAL；关闭下列 P0/P1 后可进入 DEV-B0。

## P0

1. §26 前端存储豁免与 PRD 隐私边界需要明确分层。
2. §15/§24/§30 的历史“可启动 M0”会误导实施者。
3. VRAM 指标缺少唯一、可复核的测量口径。
4. AC-13 “未声明出站为 0”缺少允许集合定义。
5. CosyVoice2 候选与 CosyVoice-300M fallback 混用。

## P1

- 后端日志脱敏门、AC 延迟与温箱漂移、400ms/1000ms 打断语义需要统一。
- §22/§28 端点表、recover API/UI 验收入口需要唯一化。
- FR-19 Should、BGE 512维、sqlite-vec fail-closed、磁盘<10GB阻断需要固化。
- 真实30条语料、1小时操作脚本、VAD故障语料需要落盘。
- consent blocked 审计事件、WS turn_id 宽度和 B4 真实 session 来源需要明确。

## 防虚假验收结论

现有 223 PASS / 4 SKIP 只证明基础单元与合同未回归。模型跳过、清单状态和文件存在均不能作为 B0 真机通过证据。

完整原始输出保存在本次自动化会话记录中；本文件只保存可执行结论，避免复制无关推理文本。
