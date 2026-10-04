# B2.5-O3 CosyVoice TensorRT验收标准

**日期**：2026-09-25  
**状态**：开发前门禁已锁定

| ID | 场景/操作 | 出门门槛 |
|---|---|---|
| O3-AC-01 | 固定环境并构建engine | 版本与SHA256齐全；只使用本地ONNX；engine可删除重建 |
| O3-AC-02 | adapter以TRT和非TRT分别启动 | `TtsPort`语义一致；health真实显示engine状态且不泄漏绝对路径 |
| O3-AC-03 | 同参考音频、正确逐字稿、同30条独立TTS | 30/30非空无hang；CER≤5%；TRT首包/RTF相对非TRT有可重复净收益 |
| O3-AC-04 | 30条真实浏览器全链 | 30/30唯一播放确认；普通桶P50≤2.0秒、P95≤3.5秒 |
| O3-AC-05 | engine缺失/损坏/不匹配 | ≤3秒暴露不可用；不在线构建下载；可一轮恢复Qwen或非TRT Cosy |
| O3-AC-06 | 资源与稳态 | 项目RAM≤14GiB、VRAM≤22GiB、两侧Available≥2GiB、无持续swap-in |
| O3-AC-07 | 离线启动与对话 | 未声明出站=0；已有engine可完全离线加载 |
| O3-AC-08 | 全量回归与PRD复检 | 后端、前端、Edge合同无新增失败；P0/P1=0；Qwen回退保留 |

主观盲听仍使用既有授权人类验收门，不用Agent自评冒充；O3机器出门必须先满足全部客观门，最终默认切换ADR仍需连同盲听在O6签署。
