# V2-X3.3 实施结果：场景激活

## 当前结论

X3.3-AC01～05及AC07已通过；AC06自动部分通过，等待项目所有者审查三个新增场景的真实说话视频。未取得人工批准前，本阶段状态为`WAITING HUMAN`，不得进入X3.4。

## 已实现

- 四场景各安装一组批准Idle和talking rendition，共8条；三个新增Wav2Lip数据集均为160帧、768×432完整场景。
- SourcePack以revision CAS原子激活场景；旧revision返回409且活动状态不变。
- Gateway提供私有no-store Idle、活动场景Avatar解析和跨重启恢复。
- 浏览器只在Idle/聆听态允许切换，保留同一会话WS/turn/音频链；同场景Idle覆盖Avatar重连窗口。
- 真实Headless会话`session_ref=816`中轮换4次：session创建1次、切换期间end请求0次，最终由测试主动结束。
- 修复输出设备控件因父级transform形成错误fixed containing block、遮挡“开始对话”的真实缺陷，并加入指针命中回归。

## 真实证据

- 绑定清单：`/home/administrator/.cyberWife/v2x/scene-renditions/scene-bindings.v1.json`
- 场景切换：`/home/administrator/.cyberWife/acceptance/V2-X3.3/ui/result.json`
- 说话捕获：`/home/administrator/.cyberWife/acceptance/V2-X3.3/talking/<scene>/capture-result.json`
- 嘴部分析：`/home/administrator/.cyberWife/acceptance/V2-X3.3/talking/<scene>/analysis-result.json`
- 人工审查页：`/home/administrator/.cyberWife/acceptance/V2-X3.3/review.html`

## 自动说话结果

| 场景 | H.264帧 | 有声/静音嘴部运动比 | 黑帧 | 近似重复嘴部帧对 | 结论 |
|---|---:|---:|---:|---:|---|
| 清晨卧室 | 200 | 1.133807 | 0 | 1 | 嘴部响应PASS；自然度待人工 |
| 雨夜书房 | 209 | 1.176966 | 0 | 0 | 嘴部响应PASS；自然度待人工 |
| 花园阳光房 | 209 | 1.197184 | 0 | 3 | 嘴部响应PASS；自然度待人工 |

三段H.264序列均单调、丢包间隙为0、相对诊断最佳偏移均为80ms。清晨/花园的1/3对近似重复帧低于1.5%，不构成持续冻结，但完整披露给人工审查；X3.3不承担X8高清口型升级承诺。
