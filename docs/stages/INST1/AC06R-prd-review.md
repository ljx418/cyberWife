# INST1-AC06R PRD规格检视

| PRD规格 | 实现结果 | 判定 |
|---|---|---|
| FR-17 一键本地生命周期 | 制品prepare纳入安装器，既有start/status/recover/stop合同不变 | ALIGNED |
| FR-04/FR-15 授权写真与音色 | bootstrap必须显式同意；激活用户音色仍优先；私有文件不进Git | ALIGNED |
| FR-10 数字人连续体验 | 缺省Avatar从真实私有制品恢复；当前Crop V2启动与强制恢复通过 | ALIGNED |
| NFR-01/NFR-04 本地与隐私 | 不联网、不上传；审计结果不含路径、逐字稿、音频正文 | ALIGNED |
| NFR-03 32GiB/24GiB边界 | 未增加常驻进程或模型；仅安装阶段复制本地制品 | NO REGRESSION |
| NFR-10 许可证 | 每个模型与Cosy源码均需本地`license_accepted`；Wav2Lip商业NO-GO不变 | ALIGNED |

结论：AC06R只修复部署可移植性，不增加PRD承诺、不降低功能探针和体验门。V1仍因V1FINAL现场门和独立干净环境门未全绿。
