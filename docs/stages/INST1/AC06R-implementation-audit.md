# INST1-AC06R 实施后审计

**日期**：2026-10-06
**结论**：实现与当前机回归 PASS；独立干净环境 OPEN。

| 审计项 | 结果 | 证据 |
|---|---|---|
| 模型路径可移植 | PASS | `prepare_local_artifacts.py`从私有JSON生成Git-ignore注册表，七个V1实时逻辑模型（含Qwen TTS回退）均做存在性/类型/许可检查，文件可绑定SHA-256；升级保留verified元数据 |
| 私人素材边界 | PASS | 仓库不携带素材；音色和Avatar均要求`consent=true`，报告不存路径/逐字稿；Gateway已移除旧`user_clip_v2.wav`硬编码 |
| 启动完整性 | PASS | bootstrap音频哈希/路径边界、Avatar ID/目录结构、Cosy源码均在prepare/verify复核；数据库无active Avatar时启动器读取私有`avatar-id` |
| 原子性 | PASS | 私有目录先复制到同盘临时目录，发布失败恢复前版本；注册表临时文件后replace |
| 当前机迁移 | PASS | 仅以已有同意记录和已激活Crop V2素材生成私有bootstrap；无私有值进入Git/终端报告 |
| 真实运行 | PASS | Cosy默认四组件全部healthy；强制Avatar恢复后仍全健康；stop×2及7860/8010/8011/8090/8091归零 |
| 回归 | PASS | 后端358 passed/5 skipped；根27；Avatar13；前端build+Playwright15；V1FINAL核心3；PowerShell AST通过 |
| 外部复现 | OPEN | 当前身份不得替代新Windows用户+新WSL正式AC06报告 |

新增Critical/P0=0，新增Major=0。实测期间Windows PowerShell经WSL宿主调用在输出完成后出现宿主relay等待，受管组件本身健康且stop正常；正式AC06由Windows PowerShell直接运行，不以该WSL终端桥行为产品失败。
