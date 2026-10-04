# B2R 开发前审计

**日期**：2026-09-25  
**历史结论**：开发前PASS；Edge WebRTC阶段曾P1 BLOCKED，现已由A2关闭

## 审计意见与闭环

| 风险 | 等级 | 审计意见 | 闭环 |
|---|---|---|---|
| 用独立 aiortc 脚本冒充产品浏览器恢复 | P1 | 必须由产品 `AvatarSession` 建立/重连，Edge只调用该实体 | 已写入计划与AC03 |
| 为恢复 Avatar 阻塞或重启整套服务 | P1 | 只终止/恢复 launcher-owned Avatar，声音为主时钟 | 已写入AC02与安全边界 |
| WebRTC自动播放导致与Gateway PCM双声 | P1 | Avatar媒体元素必须静音，只显示video；声音仍由MediaSession PCM播放 | 已写入实现边界 |
| 无限重连导致任务/资源泄漏 | P1 | 单重连、上限退避、stop彻底清理，三周期检查孤儿任务 | 已写入AC03/05 |
| 使用公网STUN或外部信令 | P0 | 仅loopback offer/health，不配置公共ICE服务 | 已写入AC06 |
| 把本阶段当成B3打断通过 | P1 | B2只签OX-09；打断仍由B3 30次真实验收 | ADR-009与出门要求锁定 |

## 一致性复核

- PRD FR-10、NFR-02 与 B2-AC03～05 均被可执行步骤和硬门覆盖。
- 架构仍为浏览器→Gateway/Avatar loopback边界，`AvatarPort`与音频主时钟不改变。
- 不新增产品界面与路由，只补已批准体验所需的媒体接线。
- 当前开放 P0=0、P1=0；可进入最小实现。若真实 Edge 无法证明同页恢复，禁止以测试替身签署。

## 开发后复审

原产品合同测试与构建通过，但真实Edge→WSL WebRTC ICE无法连接；禁用mDNS及两个loopback候选改写实验均失败。该轮开放P1（`B2R-ICE-01`）作为历史证据保留。此P1随后经Chrome复验确认，并由用户批准的A2替代传输关闭；最终状态以`B2A2-result.md`为准。
