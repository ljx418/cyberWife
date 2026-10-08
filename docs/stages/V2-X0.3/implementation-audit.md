# V2-X0.3 实现后审计

**结论**：自动化实现门PASS；Critical/P0/P1=0；真实扬声器听感与同步待目标机人工验收。

- 播放链固定为`AudioBufferSource → Gain → DynamicsCompressor → FirstSoundMeter → Destination`，没有绕过既有首响遥测。
- 音量、静音和轻量压缩仅修改Web Audio节点参数，不修改服务端PCM、TTS或A/V generation合同。
- 重播只缓存当前回答PCM于浏览器内存；不发`audio.playback.started/ended`、不启动Avatar、不创建历史语音接口。
- 新回答、打断、取消generation和结束会话均停止重播source并清空缓存。
- 缓存硬上限16MiB；超限时原子清空并停止继续缓存，不影响实时播放。
- 输出设备选择仅在`AudioContext.setSinkId`存在时启用，否则明确返回`unsupported`。
- feature flag关闭时不显示输出控制，原V1播放路径仍可用。

全量回归最初暴露3个AC-11键盘旅程的测试替身缺少`createDynamicsCompressor`，页面因此进入明确错误态；补齐浏览器能力替身后36/36通过。该问题不是产品运行态缺陷，修订保留为回归合同。
