# V2-X8.0 实施结果

## 阶段状态

**AUTOMATION PASS / WAITING HUMAN AC06。** 当前默认仍是获批Wav2Lip256 `scenev2_mouth`，MuseTalk 1.5只以独立模型目录、venv和avatar ID完成串行canary，测试结束后四服务已恢复全绿。

## 已完成开发

- 四场景X3.3-R1批准后原子激活为revision 12，并完成活动蓝调客厅同输入回归。
- 口型分析器新增上半脸身份差异；支持Wav2Lip与MuseTalk不同坐标顺序，不把整脸改写或融合噪声藏在“嘴动了”结论中。
- Wav2Lip `full`整脸回贴真实A/B完成并拒绝：脸颊净扰动P95约4.2倍、锐度均值下降约12.7%。
- MuseTalk模型根和Avatar数据根改为显式环境变量；健康端点按实际engine报告logical ID和dtype。
- 修复MuseTalk运行时CPU latent未迁移到CUDA的问题；新增显式`utils`包，避免可选依赖抢占顶层模块名。
- 新增`build_musetalk_avatar.py`，从已批准完整场景数据集复用同一帧和人脸框，生成VAE latent、jaw mask、SHA manifest；不会重新检测或覆盖活动人物。
- MuseTalk 1.5主UNet、VAE、Whisper tiny、face parser以固定SHA存入私有canary目录；MuseTalk/face parser/VAE/Whisper/torchvision分别按MIT/MIT/MIT/Apache-2.0/BSD-3-Clause完成来源核对，候选保留合同同步到ComfyUI工作流总库。

## 同输入真实结果

输入SHA：`5cba0620d4ecd5ada91425eb64b8e27d3244927e859774b63602e5f0109b0340`。

| 指标 | Wav2Lip256活动基线 | MuseTalk 1.5 canary |
|---|---:|---:|
| inferfps / finalfps | 136.759 / 25.692 | 58.457 / 25.459 |
| 首帧相对首个音频包 | 670.278ms | 471.256ms |
| 最佳相对诊断偏移 | +40ms | +80ms |
| 口型-音频相关 | 0.350679 | 0.550955 |
| 有声/静音嘴部运动比 | 1.159353 | 1.273030 |
| 脸颊净扰动P95 | 0.576075 | 0.698217 |
| 上半脸身份差异均值 | 3.040327 | 2.993730 |
| 脸部锐度均值 | 177.113615 | 177.196348 |
| 黑帧/序列缺口/持续冻结 | 0/0/0 | 0/0/0 |

MuseTalk可实时且音频响应更强，身份/锐度无机器回退；jaw边界略差，连续口型自然度仍需人工看合并视频。

## 资源与恢复

- MuseTalk完整组合观测：VRAM约15.95GiB/23.99GiB；WSL/服务聚合RAM约12.35GiB，未突破本机约16GiB预算；不允许Wav2Lip和MuseTalk双常驻。
- canary停止后恢复Wav2Lip：Gateway/Avatar/LLM/Speech均healthy；活动API仍解析`scenev2_mouth`，VRAM回到约9.23GiB。
- 私有证据：`/home/administrator/.cyberWife/acceptance/V2-X8.0/`；人工页`review.html`，合并视频`wav2lip-vs-musetalk15.mp4`。

## 未签内容

AC06人工四维评分尚未签署，MuseTalk不得设为默认；其他形象仍由X3.4/X3.5逐素材验证。许可证与ComfyUI保留工作流覆盖已关闭，但体验通过后仍需正式engine迁移与回滚验收。

## 自动化回归

UX5单元5项、Avatar 18项、后端定向12项、根目录全量62项、后端全量407项（7项按环境条件跳过）、acceptance-core 4项、Playwright 51项与前端生产构建均通过。根目录与后端测试必须分别从各自项目根执行，以避免Python同名`tests`包在单一pytest进程中发生收集冲突。
