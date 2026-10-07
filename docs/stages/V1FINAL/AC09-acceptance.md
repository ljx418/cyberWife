# V1FINAL-AC09 验收标准

| ID | 场景 | 门槛 |
|---|---|---|
| AC09-01 | 当前发布冻结 | `result=PASS`且所有源码/依赖/前端/既有证据文件SHA与当前工作区相同 |
| AC09-01B | 干净clone离线前端 | `prototype/dist/index.html`及哈希资源均为Git跟踪文件；安装器不得因clone缺dist而执行在线npm安装 |
| AC09-02 | 现场证据归属 | ACC1报告schema/gate正确、workspace revision等于当前HEAD、机器与人工结果均PASS |
| AC09-03 | 现场规格 | 三轮完整、真实PCM/麦克风、一次打断/取消及后续完整轮、零错误、Avatar绑定/live/Idle、Narrator五项、嘴部实际变化、切换无闪动、Idle自然度≥4；高清/同步/嘴部自然度评分保留为V2-X基线 |
| AC09-04 | 部署证据归属 | `clean-machine`只接受AC06双身份/五项clean；`single-machine-portability`只接受AC07隔离字段、三项限制；两者revision均须等于HEAD且offline-only=true |
| AC09-05 | 部署生命周期 | AC06须prepare/源码/verify及完整生命周期；AC07须release/隔离venv/wheelhouse/制品/前端/路径合同及start×2/status/recover/stop×2全部PASS |
| AC09-06 | 缺失/过期/伪造 | 缺报告返回PENDING/退出2；字段、哈希或revision不符返回FAIL/退出1；不得被“部分通过”覆盖 |
| AC09-07 | 隐私 | 聚合报告不保存音频/对话、操作者姓名、身份哈希、素材/模型绝对路径或原报告正文 |

只有三门均PASS且退出码0，个人/研究用途V1才可从CONDITIONAL改为PASS。报告同时公开`deployment_assurance`；AC07不等于跨机器兼容证明。商业用途Wav2Lip NO-GO不受本门改变。
