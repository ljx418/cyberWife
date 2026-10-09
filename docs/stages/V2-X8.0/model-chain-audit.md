# V2-X8.0 口型任务链与模型选型审计

## 判定摘要

1. **LiveTalking不是口型模型。** 它是会话、音频特征、Avatar调度与实时传输框架；当前实际生成器是社区Wav2Lip256 checkpoint。
2. **当前不是人物抠图路线。** 场景每帧完整保留；模型接收完整256×256脸框，预测整脸，再按manifest把预测结果融合回原帧。
3. **整脸回贴不等于更完整的模型输入。** Wav2Lip本来已看到完整脸框。整脸模式只扩大输出覆盖范围，同输入实测边界净扰动和锐度显著变差，故不应激活。
4. **MuseTalk 1.5是当前最合适的实时质量候选。** 它仍使用256脸部区域，但通过VAE latent单步UNet、Whisper特征、感知/GAN/sync loss和时空采样改善清晰度、身份与同步；仓内已有对应运行代码，但本机缺权重和预处理资产，必须实测。
5. **HeyGem/Duix效果不可直接类比。** Duix-Avatar公开桌面路线是个体训练后的非实时视频合成；Duix-Mobile虽实时，但面向移动端预制avatar，自定义形象不是可本地直接替换的开放训练链。

## 当前Wav2Lip256实测

同一活动人物、蓝调客厅、8秒真实CosyVoice WAV：

| 指标 | `mouth_oval_v1`活动基线 | `full`整脸候选 | 判定 |
|---|---:|---:|---|
| finalfps | 25.692 | 25.427 | 均实时 |
| 黑帧 / 序列缺口 | 0 / 0 | 0 / 0 | 均通过 |
| 有声/静音嘴部运动比 | 1.159353 | 1.177007 | 均真实响应 |
| 脸颊边界净扰动P95 | 0.576075 | 2.422592 | 整脸约4.2倍，拒绝 |
| 脸部锐度均值 | 177.113615 | 154.610202 | 整脸下降约12.7%，拒绝 |
| 上半脸身份差异均值 | 3.040327 | 3.292387 | 整脸更差约8.3% |

结论：当前问题不是“模型只收到一个嘴部抠图”，而是Wav2Lip256本身的逐帧生成上限、固定256脸区、社区checkpoint质量与融合策略共同作用。单纯切`full`不能获得所见商业演示效果。

## MuseTalk 1.5架构冲击

保留：Gateway音频主时钟、generation取消、H.264/NVENC、WebSocket协议、Chrome WebCodecs、单Canvas表面、Idle/live原子交接。

修改：

- Avatar启动器增加显式`engine=wav2lip|musetalk15`，一次只常驻一个；
- 数据集由`full_imgs+coords+face crops`扩为`full_imgs+coords+VAE latents+face parsing masks`；
- 音频特征由mel改为Whisper tiny embedding；
- 模型注册增加MuseTalk 1.5 UNet、VAE、Whisper、face parsing依赖及SHA；
- 构建/激活记录必须绑定engine，禁止Wav2Lip数据集误交给MuseTalk；
- 质量报告新增身份保持、mask边界、有效脸部清晰度与资源峰值。

不修改：ASR/LLM/TTS内容链、对话状态机、打断语义、浏览器路由和场景/外观领域模型。

## 本机可行性

- RTX 4090 24GB；完整V1栈运行时当前观测约10.5GB已用、约13.7GB可用。
- WSL磁盘余量约826GB；MuseTalk 1.5主UNet约3.4GB，官方完整模型仓约6.8GB，磁盘不是阻断项。
- 当前Avatar venv已有PyTorch、diffusers、transformers、OpenCV和einops；仓内v1.5加载/生成代码存在。本机缺MuseTalk权重与预处理资产，且需验证当前PyTorch/CUDA版本兼容性。
- LiveTalking公开性能表给出RTX 4090 MuseTalk约72 FPS，但只能作为上游预期；本项目还同时运行LLM/TTS/ASR，AC05必须以本机组合实测签署。

## 路线决策

**推荐：保留Wav2Lip256活动基线，拒绝整脸回贴默认化；以MuseTalk 1.5作为V2-X8唯一实时高清canary。** LatentSync 1.6只作为未来离线导出候选；Duix路线保留技术观察，不纳入当前Windows浏览器+WSL可回退架构。

## 事实来源

- MuseTalk 1.5官方仓库与实时说明：<https://github.com/TMElyralab/MuseTalk>
- MuseTalk技术报告：<https://arxiv.org/abs/2410.10122>
- LiveTalking官方仓库与性能表：<https://github.com/lipku/LiveTalking>
- Wav2Lip官方研究版与许可证说明：<https://github.com/Rudrabha/Wav2Lip>
- Duix-Avatar公开离线合成边界：<https://github.com/duixcom/Duix-Avatar>
- Duix-Mobile实时移动SDK及自定义形象边界：<https://github.com/duixcom/Duix-Mobile>
- LatentSync 1.6：<https://github.com/bytedance/LatentSync>
