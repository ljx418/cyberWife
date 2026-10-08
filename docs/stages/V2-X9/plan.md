# V2-X9 开发计划：桌面沉浸模式

## 用户结果

Chrome能力满足时，用户可把cyberWife安装到桌面、从独立窗口打开并一键进入/退出全屏；主题和背景偏好继续保留。不支持安装或Fullscreen API时，原浏览器入口仍完整可用。

## 实现范围

1. 增加标准Web App Manifest、192/512图标和standalone显示声明。
2. 增加显式Service Worker注册；只缓存公开壳文件、构建哈希资产、图标和内置背景。
3. `/api/`、`/ws/`、用户图片/音频/视频、Authorization请求、`private/no-store`响应一律网络直通且不得写缓存。
4. 捕获`beforeinstallprompt`并显示渐进增强安装入口；能力缺失时显示简短说明，不阻塞使用。
5. 增加全屏进入/退出控制，监听`fullscreenchange`保持界面状态一致。
6. 由`features.pwa`统一控制新增UI与注册；关闭时保持V1根路由行为。

## 不做

- 不引入Electron/Tauri或新的后端服务。
- 不宣称断网可进行模型对话；离线缓存只负责公开页面壳。
- 不缓存任何私人正文、运行时媒体、鉴权数据或API响应。
- 不改变主题/背景现有localStorage键，避免迁移回退。

## 交付实体

- `prototype/public/manifest.webmanifest`
- `prototype/public/sw.js`
- `prototype/public/icons/*`
- `prototype/src/services/PwaBridge.ts`
- `prototype/src/App.tsx`桌面模式控制
- `prototype/tests/v2x-pwa.spec.ts`
- feature flag、构建产物和本阶段审计证据

## 回滚

关闭`features.pwa`即停止注册并隐藏入口；已注册worker由注册器在关闭时注销，不影响普通浏览器访问。若Chrome安装门失败，保留浏览器+全屏能力，不阻塞V1对话。
