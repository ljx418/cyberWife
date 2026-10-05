# V1FINAL-AC09 最终总门聚合计划

## 目标

新增一个只读、失败关闭的最终总门。它不替代物理麦克风、Narrator、人物自然度人审或干净机安装，只负责证明三类证据属于同一当前提交且全部真实通过：发布冻结、ACC1/UX6现场报告、INST1-AC06R独立环境报告。

## 实施内容

1. V1FINAL现场报告新增Git revision绑定，并要求执行前工作树跟踪文件干净。
2. 新增Python聚合器，逐文件复算发布冻结中的源码、依赖、前端工件与阶段证据SHA-256。
3. 将已验收的生产前端`prototype/dist`纳入Git发布，确保干净clone的离线prepare不触发`npm ci`联网。
4. 对现场报告复核三轮、物理输入、打断后接续、当前Avatar、Idle、Narrator五任务、三项≥4分与隐私标志。
5. 对干净机报告复核身份隔离、五项clean-before、offline-only、固定生命周期步骤及workspace revision。
6. 新增Windows入口自动解析当前用户LocalAppData中的干净机报告；输出只含门状态/错误代码，不复制音频、文本、身份哈希或私有路径。

## 顺序

合同测试失败 → revision绑定 → 聚合器与Windows入口 → 缺报告PENDING实跑 → 全量回归 → PRD/架构/状态同步 → Git冻结。
