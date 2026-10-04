#!/usr/bin/env bash
set -euo pipefail

CW_MODEL_DIR="${CW_COSYVOICE_MODEL_DIR:-/home/administrator/.cyberWife/models/tts/CosyVoice2-0.5B}"
CW_SOURCE_DIR="${CW_COSYVOICE_SOURCE_DIR:-/home/administrator/.cyberWife/src/CosyVoice}"
CW_PYTHON="${CW_COSYVOICE_PYTHON:-/home/administrator/.cyberWife/venvs/cosyvoice/bin/python}"
CW_NVIDIA_LIBS="$(find /home/administrator/.local/lib/python3.12/site-packages/nvidia -mindepth 2 -maxdepth 2 -type d -name lib -print | paste -sd: -)"

export MODELSCOPE_OFFLINE=1
export HF_HUB_OFFLINE=1
export LD_LIBRARY_PATH="${CW_NVIDIA_LIBS}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
export PYTHONPATH="backend${PYTHONPATH:+:${PYTHONPATH}}"

exec "$CW_PYTHON" tests/m3/benchmark_cosyvoice.py \
  --model-dir "$CW_MODEL_DIR" \
  --source-dir "$CW_SOURCE_DIR" \
  --reference assets/voice/user_clip_v2.wav \
  --reference-text '早上好，宝贝，快起床了，起来陪我玩' \
  --text '今天天气不错，我想和你聊聊天' \
  --qwen-baseline audit/tts_ns_ns_t1.wav \
  "$@"
