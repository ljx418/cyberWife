# V1RC1-AC04 开发前审计

**结论**：允许执行；Critical=0，Major=0。

| 风险 | 闭环 |
|---|---|
| 把服务端收到cancel当作用户已听不到 | Chrome断言activeSources归零并以浏览器单调时钟计时 |
| 在尚未播放时打断形成虚假低延迟 | 每轮要求`sources_before>0`，先确认首个真实非静音源 |
| 只测音频、不测人物 | Avatar generation推进、连接代次不变、重连次数0 |
| 取消后旧轮仍写库或污染新轮 | 独立generation-fence读取SQLite前后差异并完成真实第二轮 |
| R3改动缩短取消尾部但泄漏原生线程 | 30次后运行时task/queue与后续60分钟资源门继续检查 |

现有runner覆盖浏览器音频设备状态、服务端事件、Avatar generation与SQLite，不需弱化或新造模拟入口。
