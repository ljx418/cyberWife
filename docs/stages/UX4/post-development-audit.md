# UX4 开发后审计

**日期：2026-10-05**

**结论：P0=0、P1=0，代码与工作流可保留，允许进入后续 Avatar/口型验证。**

## 闭环结果

- 文件持久化状态覆盖 queued/generating/awaiting_approval/failed/active，API 不泄露私有路径。
- 视频哈希进入 Avatar ID，重复素材不会误用旧目录；正面图和视频均限制在任务目录内。
- 人工确认是服务端硬门，不接受前端绕过；确认执行构建与同源 active 原子切换。
- 生成前检查模型、磁盘和 8188；只停止原本健康的组件；任务结束逐项恢复。
- Windows 可访问的独立 Comfy 用户目录 `ComfyUI/user/cyberwife-runtime/<source-hash>/` 只存运行数据库和 offline Manager 配置；私人照片与视频仍留在应用私有任务目录。白盒检查没有外部 URL 运行入口。
- 首次真实生产编排完成了合格视频，但 LLM 已健康时 PowerShell 父进程未退出，且 `start -Component llama` 错误遍历全部组件，导致任务假阴性；启动器现按 Component 选择目标，编排器以功能健康门回收父进程，并加入 source SHA 绑定的校验点续跑。全新任务目录复跑 196.187 秒成功，四服务健康。

## 风险

- 人物身份和自然度仍必须逐个素材人工确认，这是设计门而非未解决自动化缺陷。
- 首次冷生成需要数分钟，期间不能实时对话；UI 已明确提示，不将其包装为实时能力。
- 商业用途继续受 Wav2Lip ResearchOnly 限制。
