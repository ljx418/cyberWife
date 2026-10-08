# V2-X9 验收标准

| ID | 操作 | 硬门 |
|---|---|---|
| X9-AC01 | 检查manifest与安装元数据 | 名称、start_url、standalone、theme/background、192/512图标完整 |
| X9-AC02 | 注册Service Worker并加载公开壳 | 仅同源GET公开静态路径可缓存；版本升级可清旧缓存 |
| X9-AC03 | 请求API/WS/私有媒体/鉴权请求 | 全部网络直通，Cache Storage中命中为0 |
| X9-AC04 | Chrome支持/不支持安装事件 | 支持时可触发prompt；拒绝/缺失时不阻断浏览器入口 |
| X9-AC05 | 进入/退出全屏及API缺失 | 状态与`fullscreenchange`一致；不支持时明确降级 |
| X9-AC06 | 切换主题和背景后刷新 | 沿用现有本地偏好且不写入Service Worker缓存 |
| X9-AC07 | feature flag关闭 | UI隐藏、worker注销、V1行为等价 |
| X9-AC08 | 全量回归 | build/Playwright/后端无新增失败 |

真实Chrome“安装到桌面→独立窗口启动→系统重启”属于V2X-AC15人工/目标机部分，自动化不代签。
