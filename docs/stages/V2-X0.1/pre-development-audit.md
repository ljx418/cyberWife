# V2-X0.1 开发前审计

**结论**：PASS；Critical/P0/P1=0，可进入实现。

| 风险 | 等级 | 闭环 | 状态 |
|---|---|---|---|
| 提高阈值导致用户说话漏识别 | P1 | 百分位推导+上下界；后端VAD权威；一键恢复V1 | CLOSED |
| 换设备留下两条麦克风track | P1 | 串行stop旧session后start；快照和浏览器测试硬门≤1 | CLOSED |
| PTT键卡住持续采集 | P1 | pointerup/cancel/blur/visibilitychange统一release | CLOSED |
| 校准录音被保存/上传 | P0 | 只在AudioWorklet/Analyser内计算RMS，不创建Blob，不调用API | CLOSED |
| 浏览器标签隐藏后仍许可PTT | P1 | 页面隐藏强制release，生命周期阶段继续复测 | CLOSED |
| 无物理声场却签AC09 | P1 | 自动化只签结构门；误触率/插话P95必须真实声场 | CLOSED |

未发现必须扩大到后端模型或V2-A设备档案的风险。
