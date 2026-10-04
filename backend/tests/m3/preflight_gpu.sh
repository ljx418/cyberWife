#!/usr/bin/env bash
# M3 Q3 GPU 实测门 — 启动 M3 前必须通过
# 任一检查失败 → exit 1，立即停下征询用户

set -e

echo "=================================="
echo " M3 Q3 GPU 实测门"
echo "=================================="

# 1. nvidia-smi
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "[FAIL] nvidia-smi not found"
    exit 1
fi
echo "[1/6] nvidia-smi:"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv | head -3

# 2. torch.cuda.is_available()
echo "[2/6] torch.cuda.is_available:"
python3 -c "
import torch
print('  cuda available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('  device:', torch.cuda.get_device_name(0))
"

# 3. VRAM total
echo "[3/6] VRAM total:"
python3 -c "
import torch
if torch.cuda.is_available():
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f'  total_gb: {total_gb:.1f}')
    if total_gb < 22:
        print('[FAIL] VRAM < 22GB, M3 GPU 实测条件不满足')
        exit(1)
else:
    print('[FAIL] cuda not available')
    exit(1)
"

# 4. llama-server 二进制存在
echo "[4/6] llama-server.exe:"
if [ -f "/mnt/c/tools/llama.cpp/llama-server.exe" ]; then
    ls -lh /mnt/c/tools/llama.cpp/llama-server.exe | head -1
else
    echo "[FAIL] llama-server.exe not found at C:\\tools\\llama.cpp\\llama-server.exe"
    exit 1
fi

# 5. GGUF 模型存在
echo "[5/6] Qwen3-14B GGUF:"
if [ -f "/mnt/c/ComfyUI-aki-v2/ComfyUI/models/LLM/Qwen3-14B-Q4_K_M.gguf" ]; then
    ls -lh /mnt/c/ComfyUI-aki-v2/ComfyUI/models/LLM/Qwen3-14B-Q4_K_M.gguf | head -1
else
    echo "[FAIL] GGUF not found"
    exit 1
fi

# 6. cyberWife 写真资产存在
echo "[6/6] cyberWife 私有资产:"
ls -la /home/administrator/.cyberWife/assets/portrait/ 2>&1 | head -3

echo ""
echo "=================================="
echo " Q3 GPU 实测门 PASS"
echo " M3 可启动"
echo "=================================="
