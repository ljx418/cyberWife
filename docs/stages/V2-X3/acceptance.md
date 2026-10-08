# V2-X3 验收标准

| ID | 操作 | 硬门 |
|---|---|---|
| X3-AC01 | 首次启动登记4个内置场景 | 稳定UUID、真实SHA、焦点/安全区、label完整；重复启动幂等 |
| X3-AC02 | 从source-pack建立2个外观 | 仅用户标签分组；source引用完整；confirmed=true |
| X3-AC03 | 会话中切换3场景×2外观 | session/turn不变；成功后单人物单舞台；错误素材泄漏为0 |
| X3-AC04 | 注入CAS/缺失素材失败 | 页面保持上一场景/外观；active revision不变；无黑帧 |
| X3-AC05 | 刷新及重启服务 | active_scene_id/active_appearance_id与舞台恢复一致 |
| X3-AC06 | 场景Idle缺失 | 回退背景+当前人物；不创建第二人物层 |
| X3-AC07 | feature flag关闭 | 正式预设UI/API关闭，原本地背景入口可用 |
| X3-AC08 | 全量回归 | build/Playwright/后端无新增失败 |

V2X-AC03最终需以真人外观和实际Idle/说话态人工检查场景一致性；自动化不代签光影与审美融合。
