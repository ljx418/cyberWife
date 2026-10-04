# M0 环境与模型验证脚本

**作用**：按 `model-manifest.md §3` 七步核验（discovered → hashed → licensed → loadable → verified），
对 V1 6 个必装组件做最小 smoke test。

**运行方式**：
```bash
cd /mnt/c/workSpace/cyberWife
python -m tests.m0.verify_all            # 全部
python -m tests.m0.verify_llm            # 单个
```

**前置**：
- 已设置 `config/model-registry.local.yaml`（Git ignore，本机私有）
- WSL2 Python 已装：`pip install llama-cpp-python faster-whisper torch transformers sentence-transformers silero-vad onnxruntime`
- 模型文件已就位（按 `model-manifest.md §1` 路径）

**输出**：
- 每个 `verify_xxx.py` 退出码 0 = pass
- 输出 `model-registry.local.yaml` 报告：每行包含 `sha256/license_id/verified_at/status`
- 任一失败阻断 M1 启动