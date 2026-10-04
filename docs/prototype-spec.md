# cyberWife V1 原型与目标交互规格

**版本**：1.2　**日期**：2026-09-25　**状态**：G-UX冻结；B3～B5真实接线规格  
本文件定义目标体验以及当前可点击原型如何映射到真实实现。原型中的“就绪”、时延、显存、对话和记忆均为模拟，不构成模型集成证据。

## 1. 体验意图

主界面是一间安静、私密、有呼吸感的数字空间。人物是视觉重心，字幕和状态退居辅助；用户应先感到“她在这里”，再看到控制。正常对话不出现模型名、端口或日志，只有发生故障并进入“运行状态”后才展示诊断信息。

目标体验闭环：**一次点击开始 → 自然说话 → 看见她理解并回应 → 可随时插话 → 清楚控制记忆与退出**。

## 2. 当前原型与目标实现边界

| 原型实体/行为（已实现） | 当前证据 | V1 真实行为（待开发） | 责任实体 |
|---|---|---|---|
| `App` 内六态 UI | `prototype/src/App.tsx` | 由服务端事件驱动，拒绝非法/过期状态 | `ConversationScreen` + `ConversationClient` |
| `setTimeout` 模拟 thinking/speaking | 1 秒定时器 | VAD/ASR/LLM/TTS/Avatar 流水线 | `TurnPipeline` |
| 内存 `defaultMemories` | 刷新丢失 | SQLite + FTS5 + sqlite-vec | `MemoryService` |

> 当前代码事实：`prototype/src/main.tsx` 默认仍进入旧 M2 上传/设置壳，已批准的沉浸式 `App.tsx` 需要显式开关。B5 必须把沉浸式页面恢复为产品默认入口，旧入口仅保留在开发模式；这属于合同接线修复，不是视觉重设计。

### 2.1 V1 页面与组件关系

V1 是单文档状态驱动应用，不新增路由框架：`/` 根据 onboarding 完成状态显示首次设置或陪伴主屏；设置抽屉的“人物、声音与人设、记忆、隐私、运行状态”是标签页，不是独立 URL。评审页中的锚点导航只服务文档浏览，不属于产品路由。

组件边界固定为 `App/AppShell → OnboardingFlow | ConversationScreen → VoiceOrb + TranscriptOverlay + AvatarSession`，以及全局 `SettingsDrawer → MemoryPanel | PrivacyPanel | RuntimeHealthPanel`。服务层为 `ConversationClient/MediaSession/AvatarSession/HostBridge`，不允许组件直接访问模型进程。
| `runtimeServices` 固定 ready | 静态数组 | 聚合真实探针并显示 ready/loading/degraded/error | `HealthAggregator` |
| 文件选择控件 | 不读取文件 | 校验、私有复制、预处理、预览与版本回退 | `AssetService` |
| 主题 `localStorage` | 跨刷新有效 | 保留；其他设置经 API 持久化 | `SettingsService` |
| 删除确认 | 仅删内存项 | 源记录、FTS、向量和派生缓存原子删除 | `RetentionService` |
| Tweaks/模拟错误 | 仅评审入口 | 仅开发模式保留，发布构建隐藏 | 前端构建配置 |

## 3. 信息架构

```text
首次设置
├─ 01 本地与授权
├─ 02 运行检查
├─ 03 人物形象
├─ 04 声音样本
└─ 05 人设关系

沉浸主屏
├─ 人物画面 / 降级静态画面
├─ 当前对话状态与实时字幕
├─ 语音球（开始 / 结束 / 打断 / 重试）
└─ 设置抽屉
   ├─ 人物
   ├─ 声音与人设
   ├─ 记忆
   ├─ 隐私
   └─ 运行状态
```

## 4. 首次设置规格

| 步骤 | 用户操作 | 成功反馈 | 失败/跳过 | 持久化 |
|---|---|---|---|---|
| 本地与授权 | 阅读并勾选授权 | “已确认，仅用于私人非商业用途” | 未勾选不能导入真人素材 | 授权版本、时间、撤销时间 |
| 运行检查 | 点击检查/重试 | 每组件真实状态和可操作结论 | 失败可查看原因；允许用占位资源继续，但核心链路未就绪不可完成最终验收 | 最近检查结果、版本 |
| 人物形象 | 选择、裁切、预览、保存 | 待机画面可预览 | 格式/尺寸不符给修复建议；可跳过 | 资产版本与 active 指针 |
| 声音样本 | 选择音频、填逐字稿、输入试听文本 | 可试听且明确“未保存/已保存” | 噪声、时长、转录不匹配分别提示；可跳过 | 资产版本、逐字稿、试听状态 |
| 人设关系 | 填名称、称呼、性格、背景、示例 | 摘要确认后进入主屏 | 必填项就地提示；返回不丢内容 | Profile 与草稿 |

任一步关闭或异常退出后，下次回到最后完成步骤。真人资产导入永远受授权门槛约束。

## 5. 主屏与响应式布局

- **1920×1080**：人物脸部落在横向 68–82%、纵向 20–45%；字幕最大宽 560px；语音球底部居中。
- **1366×768**：字幕最大宽 440px；隐藏次要运行信息；抽屉宽度≤40vw。
- **420×720**：人物居中偏上；字幕最多三行；语音球固定安全区；设置为全高覆盖层。
- 三档视觉方案仅用于评审：Cinematic 为发布默认；Quiet 强化可读性；Signal 不进入 V1 发布构建。
- 抽屉打开时人物脸部不可被模糊；关闭后焦点回到“设置”。

## 6. 对话状态与事件

| 当前状态 | 进入事件 | 画面/文案 | 主操作 | 合法后继 |
|---|---|---|---|---|
| `idle` | 初始化/用户结束 | 轻呼吸，“今晚想聊点什么？” | 开始对话 | listening/error |
| `listening` | 开始/打断完成 | 真实输入声波，“我在听” | 结束对话 | thinking/idle/error |
| `thinking` | `utterance.final` | 克制微光，“让我想想” | 取消 | speaking/interrupted/error/idle |
| `speaking` | `reply.audio.started` | 逐句字幕、人物口型 | 打断她 | interrupted/listening/idle/error |
| `interrupted` | `barge_in.detected` | 声波收束，“嗯，你说” | 无需二次点击 | listening/error |
| `error` | 不可恢复组件故障 | 人物仍可见，说明影响 | 重试/查看状态 | 前一安全状态/idle |

完整 6×6 合法转换矩阵（其余边为不允许非法跳转，由 `ConversationOrchestrator` 拒绝并丢弃迟到事件）：

```text
         idle  listening  thinking  speaking  interrupted  error
idle      —      ✓          ✗         ✗         ✗          ✓
listening ✓      —          ✓         ✗         ✗          ✓
thinking  ✓      ✓          —         ✓         ✓          ✓
speaking  ✓      ✓          ✗         —         ✓          ✓
interrupted ✗    ✓          ✗         ✗         —          ✓
error     ✓     ✓          ✓         ✓         ✓          —
```

非法转换举例：speaking→thinking（不保存中间 turn）；error→speaking（不允许跳过 listening/thinking）；idle→thinking（无中间状态）。非法转换对应迟到事件被 `event_seq` 或 `turn_id` 丢弃；UI 不动画。

每次状态事件携带公共 envelope `{type, session_id, turn_id?, event_seq, occurred_at, payload}`（6 字段完整；详见 `target-architecture.md §6`），含 `session_id`、单调递增 `turn_id`、`event_seq`。前端忽略小于当前 turn 或 event_seq 不大于已见的迟到事件。打断时 Gateway 先发 `barge_in.detected` + `turn.cancelled`，Speech Worker 停播，Avatar 清空帧队列，LLM 请求取消；只有全部收到或超时后才开始新 turn。各组件打断 deadline：AudioContext stop ≤ 400ms、LLM cancel + Avatar 队列 drain ≤ 1s。WS 事件合同与帧格式见 `implementation-contracts.md §7`。

## 7. 字幕、音频与打断体验

- 用户字幕在 ASR final 后出现；可选显示低调的 partial，不把不稳定文本写入会话。
- 角色回答按语义分句；已确认分句显示并送入 TTS，禁止朗读 Markdown、emoji 和动作括号。
- 音频为体验时钟，Avatar 视频追随音频；视频迟到可丢帧，不可阻塞音频。
- 用户说话超过 VAD 门槛即触发 barge-in；P95 400ms 内静音。旧 turn 的字幕、音频、帧和记忆候选全部作废。
- 浏览器收到 `barge_in.detected` 后按 generation 停止已调度的旧 `AudioBufferSourceNode`，但不关闭或暂停麦克风输入；`turn.cancelled` 后再呈现 listening。
- 网络/组件短暂波动时保留当前人物与已确认字幕，不闪回空白页。
- 浏览器侧音频采集合同（AudioWorklet + 20ms PCM Int16 LE 16kHz 单声道 + WS 二进制帧）见 `implementation-contracts.md §7`。
- Avatar H.264 WebSocket帧、WebCodecs解码、有界队列与同页恢复合同见`implementation-contracts.md §8`。

## 8. 设置与数据控制

- **人物**：预览新资产后才可激活；激活失败保留旧版本。
- **声音与人设**：修改后必须显式保存；关闭有脏数据时弹出“放弃/继续编辑”。
- **记忆**：搜索结果展示正文、来源会话、时间、编辑标记；编辑后同步重建向量。
- **本次不记录**：会话前可直接启用；会话中启用需二次确认并对整场生效，启用后本场不可恢复记录。界面不得只隐藏数据而不执行后端补偿删除。
- **全清记忆**：默认焦点放在取消按钮；确认后等待后端原子事务结果，失败不得先从UI移除记录。
- **隐私**：“本次不记录”在本次会话内保持明显可见；会话结束恢复用户默认值。
- **运行状态**：首屏只显示“可用/正在准备/已降级/需处理”；技术详情二级展开。
- **危险操作**：删除单条和清空全部均二次确认；完成后显示已删除范围，不提供虚假撤销。

## 9. 故障与降级矩阵

| 故障 | 用户看到 | 仍可做 | 恢复操作 |
|---|---|---|---|
| 麦克风拒绝/缺失 | “无法听见你” | 设置、文字查看 | 打开系统权限/重新检测 |
| ASR 不可用 | “语音识别未启动” | 设置、记忆管理 | 重启 Speech Worker |
| LLM 不可用 | “暂时无法组织回答” | 已有记录与设置 | 重启 llama-server |
| TTS 不可用 | “暂时只能用文字回应” | 文字对话链路 | 重载 TTS；成功后续接新轮次 |
| Avatar 不可用/FPS 低 | 静态人物 + “画面已简化” | 完整语音对话 | 重启 Avatar/降低画面规格 |
| Embedding 不可用 | “新记忆稍后整理” | 对话和 FTS 搜索 | 恢复后处理待办队列 |
| 磁盘<10GB | “空间不足，停止缓存” | 不记录对话 | 清理过期记录/更换路径 |

## 10. 视觉与无障碍

色彩与字体沿用现有 Token：深色画布 `#071018`、强调色 `#8fc6c9`、暖色 `#d3a06f`、危险色 `#d58d86`；禁止紫粉霓虹。控件最小 44px，正文/背景达到 WCAG AA。

- 状态变化使用 `aria-live="polite"`；不可恢复错误使用 `role="alert"`。
- 所有操作可用键盘完成；模态框实施焦点圈闭并在关闭后恢复触发点。
- `prefers-reduced-motion` 关闭呼吸、扩散和滑动；信息不只依靠颜色表达。
- 屏幕阅读器文本不得泄露隐藏技术日志或重复朗读流式字幕。

## 11. HostBridge 与 V2 边界

V1 浏览器实现只返回 `browser`，其余方法为可观察的安全空操作；业务组件不得导入 Tauri/Electron API。Docker 不属于本交互规格的 V1 实现或验收条件；V2 只替换部署与进程适配，不改变以上用户旅程、状态事件和 REST/WebSocket 契约。

```ts
interface HostBridge {
  getWindowMode(): Promise<'browser' | 'compact' | 'pet'>
  setWindowMode(mode: 'browser' | 'compact' | 'pet'): Promise<void>
  setAlwaysOnTop(enabled: boolean): Promise<void>
  setTransparent(enabled: boolean): Promise<void>
  quit(): Promise<void>
}
```

## 12. 原型评审与 V1 验收的区别

卸载与数据清除是两个独立动作：卸载默认保留 `~/.cyberWife` 用户数据；“清除我的全部数据”只能从设置的危险区发起，二次确认明确列出资产、会话、记忆、备份和不可恢复性。卸载器不得通过预勾选或含糊文案把两者合并。

- 原型评审验证信息结构、文案、焦点、响应式和危险操作确认。
- V1 验收必须使用真实麦克风、模型、持久化与故障注入；原型的定时器、固定“就绪”和模拟显存不能计入。
- 当前原型通过的操作：授权门槛、六态展示、设置抽屉、记忆删除确认、主题切换。
- 当前原型未证明的能力：文件处理、模型加载、连续语音、真实打断、口型同步、记忆持久化、删除一致性、断网和长期稳定性。
