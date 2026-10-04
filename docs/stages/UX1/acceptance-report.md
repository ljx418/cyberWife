# UX1 验收报告：写真一致性、停止恢复与画幅

**日期：** 2026-10-05  
**结论：PASS。**

## 真实证据

- 当前活动写真：`portrait/be1e91a306bd47f49cb2c26f205654cc.png`，SHA256 `c0cf2628911787038e8694a9419316ea22be10a7f7dc807a2379851935358db4`。
- 当前活动 Avatar：`wav2lip256_p_c0cf262891178703`；数据库中 `asset.sha256 == avatar.source_sha256`。
- Windows 原生 Headless Chrome 154 + WebCodecs：活动 Avatar 首帧 897ms；5 秒内解码 129 帧；媒体 25fps；队列 0；丢帧 0；NVENC H.264；画布 512×768 且非空。
- 停止后：Canvas `hidden=true`、`opacity=0`、`layer=static`，写真层立即可见，不再留下黑色不透明画布。
- 响应式/辅助功能：1920×1080、1366×768、420×720 无横向溢出，axe critical/serious=0。
- 证据：`audit/v1/UX1/h264-active-avatar.json`。

## 自动化结果

- 写真/Avatar 原子激活、故障注入回滚、上一版恢复、撤销授权：PASS。
- 非法 Avatar ID 被白名单拒绝；数据集只从固定 Avatar 根读取：PASS。
- Prototype 生产构建：PASS；Playwright 10/10。
- Avatar worker：11/11。

## PRD 检视

FR-04、FR-10、FR-15 与 AC-06 的本轮增量均有真实代码和浏览器证据支撑。此结论只覆盖写真一致性、实时帧、停止恢复与安全画幅，不把待机生成视频外推为已完成。
