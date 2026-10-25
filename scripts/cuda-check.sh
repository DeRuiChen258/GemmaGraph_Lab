#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLKIT="${CUDA_TOOLKIT_ROOT:-/usr/local/cuda-13.4}"
COMPILER="$TOOLKIT/bin/nvcc"
if [[ ! -x "$COMPILER" ]] || ! "$COMPILER" --version | grep -q 'release 13\.4,'; then
  echo "需要官方 CUDA 13.4 nvcc：$COMPILER" >&2
  exit 2
fi
mkdir -p "$ROOT/.runtime"
"$COMPILER" --std=c++17 -O2 -arch=sm_120 \
  "$ROOT/scripts/cuda-probe.cu" -o "$ROOT/.runtime/cuda-probe"
echo "CUDA 13.4 / sm_120 编译通过；正在执行 GPU 内核检查。" >&2
exec "$ROOT/.runtime/cuda-probe"
