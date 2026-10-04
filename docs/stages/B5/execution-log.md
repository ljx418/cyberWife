# B5 自动化开发与验收审计记录

**执行日期**：2026-09-26  
**当前状态**：B5.1～B5.6全部PASS；V1个人/研究用途GO，商业用途NO-GO。

| 子阶段 | 开发前审计 | 实施 | 真实验收 | PRD检视 | 状态 |
|---|---|---|---|---|---|
| B5.1 完整性 | P0/P1=0 | 已完成 | B5-AC00真实HTTP/DB/Chrome PASS | FR-02/04/05/06/11/19 PASS | PASS |
| B5.2 故障恢复 | P0/P1=0 | 已完成 | 真实受管进程×4、3轮/12场景 PASS | FR-03/15/17、AC-12 PASS | PASS |
| B5.3 离线隐私 | P0/P1=0 | V1云服务硬关闭与白盒审查已实现 | 真实链/隐私/连接采样/出站白盒PASS | AC-13 PASS | PASS |
| B5.4A 主页面真实对话 | P0/P1=0 | 已完成 | Chrome `getUserMedia` 虚拟麦克风注入授权真实WAV，3轮完整播放PASS | FR-07/08/09媒体链PASS；物理声卡未覆盖 |
| B5.4B 设置真实闭环 | P0/P1=0 | 已完成 | 隔离Chrome五步5/5、no-record迁移、真实Cosy试听PASS | FR-01～06/11/13 PASS | PASS |
| B5.4C 发布组合 | 4项P1已关闭 | 已完成 | AC-01～13、AC-04A、OX-01～12同候选PASS | 无规格漂移 | PASS |
| B5.5 生命周期发布 | P0/P1=0 | 已完成 | 60分钟、数据生命周期、start/recover/stop PASS | AC-14/NFR资源PASS | PASS |
| B5.6 冻结 | 3项P1已关闭 | 已完成 | 一键、静态UI、回归、7实时+10离线形象模型/工作流、清单PASS | 全PRD逐项PASS | PASS |

## 2026-10-04 B5.5正式出门

- 数据生命周期：隔离真实SQLite/文件/hash的备份、恢复、卸载保留数据、精确确认清除全部PASS。
- AC-14 r7：60分钟、20完整+10打断PASS；RAM峰值13637.137MiB、GPU 11.557GiB、Windows/WSL余量最低4508.430/9199.871MiB。
- 后30分钟斜率：RAM +0.7303MiB/min，task/线程/三类queue=0，延迟 -1.2826ms/min。
- start×2 PID不变；Avatar强制恢复仅目标PID变化；stop×2后端口/PID记录0。后端268 passed/4 skipped、Avatar9 passed、前端构建PASS。
- 当时阶段门：B5.5开放P0/P1=0并解锁B5.6；该等待状态现已由下方B5.6最终出门记录关闭。

## 2026-10-04 B5.6最终出门

- Gateway直接托管生产前端；根目录一键启动/停止入口完成真实Windows→WSL验证，重复启动PID不变、停止两次归零。
- 后端326 passed/4 skipped、Avatar发布环境9 passed、Playwright 9 passed、生产build PASS。
- 7个实时ACTIVE模型与10个离线形象模型共同与ComfyUI保留索引精确一致；Silero JIT固定实测SHA；发布清单连续两次一致且无私有绝对路径。
- FR-01～20、NFR-01～10、AC-01～14、AC-04A、OX-01～12逐项PASS，开放P0/P1=0。V1个人/研究用途GO；Wav2Lip限制使商业用途NO-GO。

## B5.1开发前验收标准与审计

- 授权：真实POST/DELETE后DB和审计一致；未授权上传/激活均403；撤销移除active pointer且文件仅软禁用。
- 资产：人物与声音各至少2版；列表、预览、激活、失败不切换、恢复上一版均由真实文件与DB证明。
- 人设：六字段保存、历史快照、并发冲突409、进程重启后一致。
- 页面：Chrome根路由默认批准主舞台；`?legacy=1`仅开发入口；六类设置逐项请求真实API，禁止示例数据冒充。
- HostBridge：浏览器方法统一返回明确`unsupported`结果，不触发本机特权。
- 开放审计：当前代码缺口与计划完全对应，无需架构扩展；P0/P1=0，允许实施B5.1。

## B5.1结果与B5.2开发前审计

- 首轮`audit/v1/B5/B5-AC00/result.json`因Vite旧进程返回缓存模块导致Chrome定位失败，HTTP/DB项已过但未签署；重启Vite后正式证据`audit/v1/B5/B5-AC00-final2/result.json` PASS。
- 未授权上传403；人物/声音各2版，激活与上一版恢复真实文件/DB通过；撤销后active=0且再次上传/激活403；三点激活故障回滚合同通过。
- 完整人设version 1→2、旧version 409、历史快照和进程重启一致；Chrome 153确认根路由主舞台、开发legacy入口、六页签七类真实API响应及HostBridge明确unsupported。
- B5.2固定以PowerShell受管PID与functional probe为恢复事实源；Gateway不得仅切换UI状态。Speech进程承载ASR/TTS/Embedding，故单项恢复映射到同一受管Speech进程但恢复后分别重跑三个功能探针。页面2秒轮询，≤3秒显示故障影响和恢复动作。
- PowerShell只终止PID记录与命令行marker匹配的项目进程；外部端口所有者继续fail-closed。开放P0/P1=0，允许实施B5.2。

## B5.2结果、事故闭环与PRD检视

- 最终证据：`audit/v1/B5/B5.2-recovery-final/result.json`。Windows Chrome 153、真实PowerShell受管PID、真实模型，LLM/Speech/Avatar/Gateway各3次故障，共12/12 PASS；页面刷新0次。
- 故障显示：LLM/Speech/Avatar后端降级83～248ms；Gateway不可达2.65～2.76秒；Chrome原页均显示正确`error`或“Gateway不可达”。Gateway/CosyVoice完整重载48.45～65.57秒，恢复后功能探针ready。
- 失败证据保留：`B5.2-recovery-diagnostic-v3/v4`与`B5.2-ui-debug*`记录旧Vite转换缓存导致的页面假ready；正式验收重启Vite并关闭HTTP缓存后通过。产品请求增加`cache: no-store`，避免发布环境复用状态快照。
- 审计发现并修复TTS宿主语义：CosyVoice实际位于Gateway，不再以Speech Worker存活冒充TTS；同时禁止`/health`内部自请求形成递归，TTS只能由真实非静音合成功能探针提升ready。
- PRD检视：FR-03真实状态、FR-15单项恢复、FR-17恢复入口、AC-12的≤3秒可见/同页恢复/无假ready均满足。故障恢复耗时如实报告，不冒充≤3秒；该3秒门仅约束影响与动作可见。
- 开放P0/P1=0。PowerShell包装进程句柄残留为P2运维债，纳入B5.5 stop后PID=0硬门，不影响B5.3隐私实施。

## B5.3开发前计划、验收标准与审计

- 实施：增加单一隐私验收runner，采集Windows/WSL监听端口、项目PID归属、DNS/HTTP/TCP已建立连接、运行时离线环境、日志/工作区敏感正文、私有资产、数据库/模型误入库和新原始音频文件。
- 真实流程：在离线严格配置下启动/复用发布候选，使用授权真实音频完成5轮ASR→LLM→CosyVoice→Avatar会话，并执行真实记忆搜索、编辑、删除和本地资产版本操作；不得用HTTP smoke替代对话。
- 网络门：所有服务只监听127.0.0.1/::1；允许集外、归属于项目进程的DNS/HTTP/TCP established为0；无STUN；默认V1运行面白盒不存在可达公网出站动作。用户已明确物理断网会中断宿主终端，因此不执行该脚本，也不再作为AC-13门槛。
- 数据门：验收前后音频文件集合无新增原始麦克风音频；日志与代码工作区不出现本次唯一敏感标记、完整逐字稿、私有资产或运行数据库；扫描输出只保存路径、规则ID和哈希，不复制正文。
- 失败处置：任一外联、非loopback监听或敏感内容命中为P0并停线；离线模型缺失、五轮链失败、审计采集不完整为P1并退回本计划。审计确认当前实现边界明确，开放P0/P1=0，允许进入B5.3。

## B5.3执行结果与停线审计

- 失败证据`audit/v1/B5/B5.3-privacy-initial/failure.json`：5轮完成后Windows连接归属工具因逐连接CIM查询超时，未签署。
- 第二轮`audit/v1/B5/B5.3-privacy-final/result.json`：5/5真实ASR→LLM→CosyVoice→Avatar通过、真实sqlite-vec记忆列出/编辑/搜索/删除通过、原始音频增量0、日志正文命中0；但`ss`列解析把Process误作peer，且发现旧无监听Gateway进程未带offline变量，因此FAIL。旧PID经命令行和无监听事实精确确认后终止；当前受管Gateway未受影响。
- 第三轮`audit/v1/B5/B5.3-privacy-final2/result.json`：5/5、Avatar 1075帧、160次网络采样、五端口仅loopback、允许集外established=0、三个模型进程离线变量全真、音频增量0、日志命中0、临时向量记忆五项操作全真，应用控制PASS。
- 用户在2026-09-26明确修订验收方式：物理断网会连带中断宿主终端，脚本无需执行；采用功能完备性与白盒有无联网上传动作进行验证。旧`RunOfflinePrivacyAcceptance.ps1`已删除，`accept_privacy.py`不再伪装物理隔离证据。
- 白盒修复：V1配置硬关闭上游云服务且无再开启CLI；强制`external` PCM、空STUN/push/云LLM；Gateway和LLM适配器拒绝非回环LLM；默认Avatar只注册必要媒体路由。实测`/human`、`/api/avatar/task`、`/api/asr`、`/api/admin/config`均404，活动运行文件公网URL字面量0。上游可选云模块仍以不可达源码保留并披露。
- 最终证据`audit/v1/B5/B5.3-egress-whitebox-final/result.json`与`B5.3-privacy-final3/result.json`：19项相关回归通过（另4项按环境跳过）；5/5真实链、Avatar 1071帧、159次采样、公网established=0、原始音频增量0、敏感日志命中0、记忆CRUD全真。AC-13 PASS，开放P0/P1=0，允许进入B5.4。
# 2026-10-03 B5.4C恢复记录

- 中断前的20轮真实模型连续链已完整落盘并PASS（20/20），终端中断没有破坏证据。
- 关闭4项开发前P1：真实健康状态、错误码前缀、焦点圈闭/对比度、Cosy→Qwen单向启动fallback。
- 修复`RuntimeLauncher restart -Component`误重启全部组件且丢失配置的问题；单组件restart改走强制recover并透传全部运行参数。
- 历史停止点（已解除）：当时受管终端策略禁止AF_INET/netlink/localhost/VSock，嵌套WSL返回`UtilBindVsockAnyPort:309`；后续环境权限恢复并完成真实四进程组合验收。

# 2026-10-04 B5.4C继续执行与AC-06停线

- 环境权限恢复，真实四进程和Windows Chrome 154可用。AC-04普通30条30/30，首响P95=6174.887ms，RAM 13.334GiB、VRAM 10.483GiB，PASS。
- 补齐命令清单缺失的`tests.b25.accept_warm_cache`；AC-04A真实命中3/3、P95=14.355ms，24负例误命中0、五维版本失效、64MiB与无持久化门PASS。
- AC-05当前候选早/中/晚各10次共30/30，浏览器静音P95=2.6ms，旧generation音频0；独立generation fence与队列收尾PASS。
- AC-06当前候选三周期FAIL：音频/文字继续、服务端inferfps>106/finalfps≈25、backlog 0、同页恢复均存在，但客户端显式静态降级首周期5229ms；旧runner另有generation和空闲期FPS测量错误，已修正等待复验。
- 尝试1秒HTTP probe、1.5秒帧watchdog及1.5秒HTTP probe，均会在真实Wav2Lip负载下误降级健康会话，造成重连风暴，实验代码已回退。仅保留降级时清空canvas显示底层静态人物的安全改动，前端build PASS。
- 按阶段规则停止：AC-06 P1未闭环，AC-07～B5.6不允许开始。推荐新增独立轻量心跳/控制通道；备选为H.264 WS heartbeat。放宽2秒门需要人类明确批准。
