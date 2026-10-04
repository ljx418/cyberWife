# B5 开发前审计与开发后复核模板

**当前结论**：B5.1～B5.6全部PASS；开放P0=0、P1=0。B5.3验收口径按用户澄清采用功能完备性、白盒出站审查与运行时连接采样，未伪造物理断网证据。

| 风险 | 等级 | 关闭方式 | 状态 |
|---|---|---|---|
| B5只跑测试但AC-01/02接口不完整 | P1 | B5.1先补授权、资产版本、人设和默认入口 | CLOSED IN PLAN |
| UI假恢复代替进程恢复 | P1 | recover API + functional probe为主证据 | CLOSED IN PLAN |
| 缓存命中污染普通首响 | P1 | 发布候选继续分桶 | CLOSED IN PLAN |
| 离线声明掩盖可达公网调用 | P0 | V1硬关闭云服务、非回环LLM拒绝、危险路由404、连续监听/连接采样 | CLOSED / VERIFIED |
| 卸载误删或数据清除无确认 | P0 | 卸载保留数据；清除独立二次确认 | CLOSED IN PLAN |
| 模型白名单状态陈旧导致误删 | P0 | 同步清单；只生成删除候选，不自动删除 | CLOSED IN PLAN |
| 旧上传页仍为默认入口 | P1 | 默认入口回归纳入AC-01/11 | CLOSED IN PLAN |

开发后追加 AC/OX 总矩阵、开放缺陷、发布物哈希和最终 Go/No-Go。任何未执行场景不得标记为 PASS。

开发后复核已落盘于`B5.6-acceptance-report.md`和`B5.6-prd-review.md`。模型/依赖/源码/生产前端/关键证据清单位于`audit/v1/B5/B5.6-freeze/release-manifest.json`。个人/研究用途V1 GO；Wav2Lip商业许可证风险没有被豁免，商业用途NO-GO。
