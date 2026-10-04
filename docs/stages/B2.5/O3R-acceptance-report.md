# B2.5-O3R 验收报告

**日期**：2026-09-25  
**结论**：PASS；关闭 `O3-RB-01`，采用非TensorRT CosyVoice默认profile，不进入O4。

## 1. 真实结果

| 项目 | 结果 | 判定 |
|---|---:|---|
| ASR源/目标逐文件SHA256 | 5/5一致，源保留 | PASS |
| ext4 Speech Worker冷启动+真实GPU转写 | 3/3非空，无incomplete错误 | PASS |
| Qwen Edge普通链 | 30/30；P50/P95=6.327/8.393s | 首响FAIL，保留回退 |
| Cosy非TRT初始对照 | 30/30；P50/P95=5.405/6.197s | 首响PASS，RAM需复核 |
| Cosy临时内存回收版 | 30/30；P50/P95=5.567/6.392s | PASS |
| Cosy质量 | 既有正确逐字稿CER=0.71% | PASS |
| 组合驻留 | RSS口径约13.14GiB；VRAM约9.37GiB；双侧余量≥2GiB | PASS |

Cosy回收版相对同轮Qwen：P50改善约12.0%，P95改善约23.8%。内存回收发生在整轮完成后，不进入首包路径；对照与回收版P95差约3.2%，未构成体验回退。

## 2. 验收项

| ID | 结果 | 说明 |
|---|---|---|
| O3R-AC-01 | PASS | 目录总字节1621665983；5文件哈希一致 |
| O3R-AC-02 | PASS | 3次冷启动墙钟约6.52/4.53/4.51s，真实转写均非空 |
| O3R-AC-03 | PASS | Cosy回收版30/30，P95=6392.207ms≤7000ms |
| O3R-AC-04 | PASS（主观项待O6） | CER与资源机器门通过；授权盲听不能由Agent代签 |
| O3R-AC-05 | PASS | Qwen/Cosy profile均已真实重启运行；源路径仍存在，无下载 |
| O3R-AC-06 | PASS | 263 passed/4 skipped、前端build PASS；无参数一键启动实际使用Cosy且真实浏览器样本5.187秒 |

## 3. 决策

ADR-008接受非TensorRT CosyVoice为V1默认，Qwen保留显式回退。TensorRT与O4高成本LLM运行时迁移不进入V1。授权声音盲听≥4/5仍是O6人类门，不据机器CER虚假签署。
