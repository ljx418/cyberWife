# B2.5-O3 CosyVoice TensorRT可逆加速开发计划

**日期**：2026-09-25  
**状态**：开发前计划已锁定

## 1. 事实与目标

O2R后普通Qwen全链P50/P95=5.913/7.827秒，TTS仍是主要瓶颈。既有CosyVoice2正确逐字稿30条CER=0.71%、独立首包P50/P95=2.55/3.43秒，但全链样本5.08秒未达门。

本机固定：RTX 4090 24GB、驱动616.92、CosyVoice源码revision `074ca6d...`、模型revision `eec1ae6...`、上游已有`flow.decoder.estimator.fp32.onnx`。O3只使用上游`CosyVoice2(load_trt=True)`加速flow decoder，不引入TensorRT-LLM/Triton Server，不改变`TtsPort`。

## 2. 实施顺序

1. 在既有CosyVoice隔离venv安装并锁定上游声明的TensorRT 10.13.3.9；记录Python、Torch、CUDA、驱动和包版本。
2. 用现有ONNX离线构建GPU专属FP16 engine到模型目录；生成包含模型/ONNX/engine SHA256、GPU、TensorRT版本的manifest。engine属于可删除派生物。
3. 先写合同测试，再让`CosyVoiceTtsAdapter`支持显式`load_trt`、engine预检和脱敏health；默认Qwen与默认Cosy非TRT路径均不被隐式修改。
4. 通过受限运行配置选择`cosyvoice2-0.5b + TensorRT`；同一时刻只驻留一个TTS，失败在一轮启动内回退Qwen。
5. 独立TTS先做1条smoke、10条筛选、30条质量/首包；随后做30条真实浏览器全链。
6. 执行缺engine、损坏manifest或反序列化失败的负例；不得在线重建、下载或伪报ready。
7. 完成资源、离线、全回归和PRD复检。若全链未达2.0/3.5秒，即使TensorRT本身有效也不得关闭B2首响门。

## 3. 回滚与停线

- `load_trt=false`恢复原Cosy PyTorch adapter；TTS选择恢复Qwen不迁移数据。
- engine与manifest可删除，源ONNX和模型权重只读。
- 构建/加载峰值不得突破VRAM 22GB或造成项目RAM>14GB；构建时停止Qwen TTS常驻但保留LLM/ASR/Avatar真实组合验收。
- TensorRT缺包、解析失败、质量CER>5%、任一样本空音频/hang、全链无净收益或资源越门即拒绝该路线并停线复审。

## 4. 交付

- 可逆adapter/runtime profile与合同测试；
- engine manifest、构建日志和失败负例；
- 同语料30条WAV、CER、首包、RTF及真实浏览器全链CSV；
- O3验收报告、PRD复检、开发后审计和明确的选中/拒绝结论。
