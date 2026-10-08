# V2-X3.3 验收报告

| 验收项 | 状态 | 证据 |
|---|---|---|
| AC01 四场景绑定安装 | PASS | 8条rendition；四个Avatar数据集各160张full/face帧；文件/清单SHA一致 |
| AC02 四场景原子激活 | PASS | revision 3→7真实API轮换；旧revision 409且状态不变；测试后恢复蓝调客厅 |
| AC03 同会话切换 | PASS | 真实Headless `session_ref=816`；1次创建、4次激活、切换期间0次end；截图齐全 |
| AC04 跨重启恢复 | PASS | Avatar/Gateway重启后revision 11、蓝调客厅、Idle URL和speaking Avatar一致；五服务READY |
| AC05 故障注入 | PASS | 旧revision、未成对/缺失/篡改绑定由CAS和三方SHA合同拒绝；合同测试覆盖 |
| AC06 真实音频说话 | WAITING HUMAN / R1 AUTO PASS | 首轮被项目所有者退回；R1四场景同音频候选的动作连续性、脸颊边界、清晰度、嘴部响应和性能自动门已通过，仍需重新观看批准 |
| AC07 全量回归 | PASS | 后端407/7、根测试60、Playwright 51、核心合同4、生产构建PASS |

阶段结论：**WAITING HUMAN，候选未激活并阻断X3.4。**
