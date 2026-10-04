# B2R PRD 规格检视

**日期**：2026-09-25  
**历史结论**：原WebRTC路线FAIL/BLOCKED；现已由用户批准的A2与`B2A2-result.md`关闭，OX-09已签署

| PRD规格 | 真实结果 | 判定 |
|---|---|---|
| FR-10 正常Avatar口型 | WSL内真实aiortc基线 inferfps=114.72、finalfps=25.006 | 模型基线PASS |
| FR-10 产品浏览器显示 | Windows Edge→mirrored WSL2 WebRTC ICE不可达 | FAIL |
| Avatar故障≤2秒静态降级 | Gateway合同存在；因产品视频链未连通，不能进行可信故障E2E | BLOCKED |
| 音频不中断、下一轮原页恢复 | 产品合同测试通过，但真实链未完成 | BLOCKED |
| 本机隐私 | HTTP/健康仅loopback；未引入公网STUN | PASS，必须保持 |

不能用WSL内aiortc、mock重连或健康端点代替Windows产品浏览器证据。本文件保留失败历史；Chrome复验、A2路线与最终产品浏览器证据分别见`B2R-chrome-revalidation-result.md`和`B2A2-result.md`。
