# V2-X0.1 实现后审计

**结论**：自动化实现门PASS；开放代码Critical/P0/P1=0；物理声场AC09仍待人工。

## 白盒检查

- `deriveInputCalibration`只接收RMS数字，P50/P95抗短脉冲；普通阈值限制0.012～0.055，打断阈值限制0.030～0.095且更严格。
- 校准链为`MediaStreamSource→Analyser→zero Gain→destination`，只保留数字数组；没有Blob、文件、REST、WS或日志写入。
- `selectDevice`先`stop()`旧track/AudioContext，再打开新设备；失败时明确恢复系统默认设备并把原错误返回UI。
- PTT未许可时每帧清boundary/preroll；释放时结束已开始utterance并清状态；pointer cancel、窗口blur和页面hidden均释放。
- 后端`/api/v1/experience/settings`只返回布尔capability flag；不返回设备ID、路径或用户数据。
- flag关闭时输入设置页与PTT不出现，`start()`仍走V1默认设备/阈值。

## 审计修正

1. 初版校准Analyser没有连接下游，真实浏览器可能不拉取音频图；已增加zero-gain下游，避免监听回声同时保证处理。
2. 初版换麦失败只抛错，没有真正恢复默认输入；已增加失败恢复并由浏览器测试验证请求序列`默认→失败设备→默认`。
3. 配置回归旧断言只允许X0合同开启；X0.1通过后更新为仅`contracts+input_calibration`开启，其余12项仍关闭。

## 未冒充的证据

无头浏览器的MediaStream是可控测试替身，只能证明资源清理、状态和UI合同，不能证明真实房间误打断下降70%或物理插话P95。该体验门保留给人工真实声场。
