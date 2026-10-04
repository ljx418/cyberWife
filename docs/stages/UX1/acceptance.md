# UX1 验收门

| 用例 | 操作 | 出门门槛 |
|---|---|---|
| UX1-AC01 写真一致性 | 上传、构建并激活写真 | active asset SHA = active Avatar source SHA；WebSocket 使用新 avatar_id |
| UX1-AC02 原子失败 | 注入构建/激活失败 | 旧写真和旧 Avatar 均保持 active，无半成品被使用 |
| UX1-AC03 停止恢复 | 连续开始/停止 20 次 | Canvas 隐藏，500ms 内显示写真，黑屏 0 次 |
| UX1-AC04 画幅 | Chrome 1920×1080、1600×900、1366×768、1024×768、420×720 | 人脸与嘴部在安全区，无横向溢出和拉伸 |
| UX1-AC05 安全 | 构造路径型 avatar_id | 连接被 422/403 拒绝，数据根外无读取 |
| UX1-AC06 回归 | Backend、Avatar、Prototype 全量自动化测试 | 无既有失败；PRD FR-04/10/15 无回退 |

