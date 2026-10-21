#!/usr/bin/env bash
set -euo pipefail
cd -- /network-volume/ProJ_VA/soande_ai
export TMPDIR="$PWD/tmp"
export XDG_CACHE_HOME="$PWD/cache"
export CUDA_CACHE_PATH="$PWD/cache/cuda"
export LLAMA_CACHE="$PWD/cache/llama"
export PYTHONPYCACHEPREFIX="$PWD/cache/pycache"
export HISTFILE=/dev/null
test -x runtime-src/build/bin/llama-server
test -f models/qwen3-8b.gguf
nohup python -B "$PWD/worker.py" >> "$PWD/logs/worker.log" 2>&1 < /dev/null &
echo "AI worker starting in /network-volume/ProJ_VA/soande_ai"
