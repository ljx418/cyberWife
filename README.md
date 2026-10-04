# cyberWife

`cyberWife` 是一个完全本地运行的沉浸式数字伴侣项目。V1 已完成实现与目标硬件真实验收，发布范围为**单用户、本机、个人/研究用途**；Wav2Lip 的 ResearchOnly 许可证使商业用途保持 No-Go。仓库不包含真实人物照片、声音或模型权重。

## 一键运行（Windows 11 + WSL2）

1. 双击根目录的 `Start-cyberWife.cmd`。
2. 等待四个本机组件通过功能探针；默认浏览器会打开 `http://127.0.0.1:7860/`。
3. 完成授权与首次设置后，可持续进行本机语音对话。
4. 结束时双击 `Stop-cyberWife.cmd`；重复停止也是安全的。

启动器只管理自己记录且命令行标记匹配的进程；若端口被其它程序占用会拒绝启动，不会结束外部进程。全部服务只监听 loopback。首次发布前端构建已包含在 `prototype/dist`；修改前端源码后需重新执行 `npm --prefix prototype run build`。

### 从照片生成动态人物

首次设置进入“人物形象”，或已完成设置后打开“设置 → 人物”：

1. 选择一张已获授权的 JPG/PNG，调整缩放和取景，点击“生成动态形象”。
2. 后台先保存静态安全版本，再临时释放 LLM、语音和 Avatar 的 GPU 资源；页面与 Gateway 保持在线。目标机一次冷生成约需数分钟，期间不能开始实时对话。
3. 页面会同时展示标准化正面照和 10 秒无缝待机视频。只有点击“确认并使用动态形象”，候选视频才会构建成实时口型数据并原子切换；取消、失败或关页都不会用未确认结果替换当前人物。
4. 生成结束后，系统恢复生成前确实在线的推理服务。候选与日志保存在应用私有数据目录，不写入 Git；ComfyUI Manager 在独立用户目录中以 `offline` 模式运行。

本功能要求本机已有 `C:\ComfyUI-aki-v2\ComfyUI` 及项目工作流引用的 Qwen Image 2.1、Wan 2.2、VAE、文本编码器和 LoRA。启动任务前会逐项检查模型、至少 5 GiB 工作盘空间和 8188 端口；缺失时明确失败且不停止实时服务。同一照片、同一已校验输出在失败重试时会复用检查点。

## 文档

- [产品需求文档](docs/PRD.md)
- [原型与交互规格](docs/prototype-spec.md)
- [V1 目标架构](docs/architecture/target-architecture.md)
- [开发与交付计划](docs/project-plan.md)
- [验收计划与出门门槛](docs/acceptance-plan.md)
- [需求追踪矩阵](docs/traceability-matrix.md)
- [模型清单与核验合同](docs/model-manifest.md)
- [8 页架构与 Gap 图（Draw.io）](docs/cyberWife-architecture-gap.drawio)
- [架构决策记录 ADR](docs/architecture/adr/README.md)

V1 固定为 Windows + WSL2 原生进程部署；Docker 容器化属于 V2，不是 V1 的开发或验收前提。模型状态在完成实际加载、功能探针、资源和离线验证前统一为“待核验”。

## 前端开发与回归

```bash
cd prototype
npm install
npm run dev
```

开发服务器打开 `http://127.0.0.1:4173/`；如需直接查看主界面，可使用
`http://127.0.0.1:4173/?preview=1`。

生产构建：

```bash
npm run build
npm run preview
```

Windows 上可使用已安装的 Microsoft Edge 执行端到端验收：

```bash
cd prototype
npm run test:e2e
```

测试覆盖首次授权门槛、设置/记忆/主题、音频确认与打断合同、三尺寸可访问性、焦点圈闭和减少动效。

原型中的人物为 AI 生成的虚构成年人，仅用于设计验证。未来接入授权素材时，请将真实照片、声音、会话和记忆排除在版本控制之外。
