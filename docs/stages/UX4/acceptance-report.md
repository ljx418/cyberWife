# UX4 验收报告：照片到动态人物

**日期：2026-10-05**

**状态：PASS；自动合同、完整生产编排、服务恢复与既有人工视觉门均通过。**

## 已取得证据

- 生产编排输入：用户提供的 `图片-1.png`（只记录文件名，不把素材写入仓库）。
- Qwen 正面化与 Wan Idle 均真实执行；源视频 81 帧、16.005fps。
- 输出：160 帧、16fps、10.000 秒；首尾 MAE=1.3957，回转点 MAE=0.0581。
- Comfy 日志明确记录 `[ComfyUI-Manager] network_mode: offline`。
- 修复后以全新任务目录执行完整生产编排，196.187 秒正常返回；结束后 LLM、Speech、Avatar、Gateway 均为 owned/healthy。
- 输出视频 SHA-256=`4c0b8a0b…e93c05`，与用户此前人工批准的 `two-stage-v2-image-1_idle_10s_loop.mp4` 完全一致，因此本轮可以继承该具体视频的身份与自然度签署，不将“相似”冒充“相同”。
- 同源检查点复跑 1.753 秒返回 `reusing_validated_checkpoint`，四服务 PID 全部不变。
- 使用该 MP4 在隔离目录真实构建 Wav2Lip 数据集：SCRFD 对 160/160 帧均检出唯一人脸，生成 160 张全帧与 160 张 256×256 face crop；manifest 为 `closed_palindrome`，脸框中值 `[125,558,112,411]`。当前 active 未被切换。

## 自动化

- 后端人物衍生与新 API：8 项相关用例通过。
- 后端全量回归：340 passed、4 skipped（4 项为当前环境明确标记的条件跳过）。
- 前端生产构建通过；最终 Playwright 11/11，通过新增照片→生成→双预览→确认路径及原有打断、黑屏回退、三视口可访问性。期间一次并行运行的焦点首断言瞬时失败，随后单用例及完整套件均通过，未隐去该重跑事实。
- Comfy 工作流静态合同 2/2；视频 Avatar builder 4/4。
- 出站白盒检查 PASS，无活动外部 URL 字面量。

## 阶段门结论

- UX4-AC01～08：PASS。
- 首次真实运行发现的“PowerShell 父进程不退出 + start 忽略 Component”假阴性已修复；定向验证确认仅启动 llama 时其余三个 PID 不变。
- 当前活动人物仍为原 `wav2lip256_idle_p_c0cf262891178703`；验收没有擅自激活新候选。
