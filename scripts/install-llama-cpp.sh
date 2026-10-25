#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME_DIR="$ROOT/.runtime/llama.cpp"
REPOSITORY="https://github.com/ggml-org/llama.cpp"
RUNTIME_REF="v0.7.0"
DEVICE="cuda"
CUDA="ON"
CUDA_COMPILER=""
CUDA_VERSION=""
CUDA_ARCHS=""
CMAKE_DEVICE_ARGS=()

case "${1:---cuda}" in
  --cpu) DEVICE="cpu"; CUDA="OFF" ;;
  --cuda) ;;
  --help|-h)
    echo "用法: $0 [--cpu|--cuda]"
    echo "从 ggml-org/llama.cpp 的 v0.7.0 构建官方 llama-completion；默认 CUDA 13.4。"
    echo "CUDA_TOOLKIT_ROOT 默认为 /usr/local/cuda-13.4，CUDA_ARCHITECTURES 默认为 120。"
    exit 0
    ;;
  *) echo "未知参数：${1}；使用 --help 查看用法。" >&2; exit 2 ;;
esac
if (( $# > 1 )); then
  echo "只接受一个设备参数：--cpu 或 --cuda。" >&2
  exit 2
fi

for tool in git cmake python; do
  command -v "$tool" >/dev/null || { echo "缺少构建工具：$tool" >&2; exit 1; }
done
if [[ "$DEVICE" == "cuda" ]]; then
  TOOLKIT_ROOT="${CUDA_TOOLKIT_ROOT:-/usr/local/cuda-13.4}"
  CUDA_COMPILER="$TOOLKIT_ROOT/bin/nvcc"
  [[ -x "$CUDA_COMPILER" ]] || { echo "找不到 CUDA 13.4 编译器：$CUDA_COMPILER" >&2; exit 1; }
  NVCC_VERSION="$("$CUDA_COMPILER" --version)"
  if [[ ! "$NVCC_VERSION" =~ release[[:space:]]13\.4, ]]; then
    echo "需要官方 CUDA Toolkit 13.4；指定 nvcc 不是 release 13.4：$CUDA_COMPILER" >&2
    exit 1
  fi
  CUDA_VERSION="13.4"
  CUDA_ARCHS="${CUDA_ARCHITECTURES:-120}"
  CMAKE_DEVICE_ARGS=(
    "-DCUDAToolkit_ROOT=$TOOLKIT_ROOT"
    "-DCMAKE_CUDA_COMPILER=$CUDA_COMPILER"
    "-DCMAKE_CUDA_ARCHITECTURES=$CUDA_ARCHS"
  )
fi

mkdir -p "$ROOT/.runtime"
if [[ ! -e "$RUNTIME_DIR" ]]; then
  git clone --depth 1 --branch "$RUNTIME_REF" "$REPOSITORY" "$RUNTIME_DIR"
elif [[ ! -d "$RUNTIME_DIR/.git" ]]; then
  echo "$RUNTIME_DIR 已存在且不是 Git checkout；请保留原目录并指定独立的官方源码目录。" >&2
  exit 1
fi

ORIGIN="$(git -C "$RUNTIME_DIR" remote get-url origin)"
if [[ "$ORIGIN" != "$REPOSITORY" && "$ORIGIN" != "$REPOSITORY.git" ]]; then
  echo "拒绝使用非官方源码 origin：$ORIGIN" >&2
  exit 1
fi
COMMIT="$(git -C "$RUNTIME_DIR" rev-parse HEAD)"
TAG_COMMIT="$(git -C "$RUNTIME_DIR" rev-parse "refs/tags/$RUNTIME_REF^{commit}")"
if [[ "$COMMIT" != "$TAG_COMMIT" || "$COMMIT" != 620d222* ]]; then
  echo "现有 checkout 不在固定官方版本 $RUNTIME_REF；安装脚本不会切换或覆盖它。" >&2
  exit 1
fi
if ! git -C "$RUNTIME_DIR" diff --quiet || ! git -C "$RUNTIME_DIR" diff --cached --quiet; then
  echo "官方源码包含本地修改；安装脚本不会覆盖修改或将其标为官方构建。" >&2
  exit 1
fi

# Remove stale provenance before a rebuild so a failed build cannot appear ready.
rm -f "$RUNTIME_DIR/build/gemmagraph-runtime.json"
cmake -S "$RUNTIME_DIR" -B "$RUNTIME_DIR/build" \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_BACKEND_DL=OFF \
  -DGGML_CUDA="$CUDA" \
  -DGGML_NATIVE=ON \
  -DLLAMA_BUILD_TESTS=OFF \
  -DLLAMA_BUILD_SERVER=OFF \
  -DLLAMA_BUILD_TOOLS=ON \
  "${CMAKE_DEVICE_ARGS[@]}"
cmake --build "$RUNTIME_DIR/build" --config Release --target llama-completion --parallel 8

python - "$RUNTIME_DIR" "$REPOSITORY" "$RUNTIME_REF" "$COMMIT" "$DEVICE" \
  "$CUDA_VERSION" "$CUDA_COMPILER" "$CUDA_ARCHS" <<'PY'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

runtime_dir, repository, ref, commit, device, cuda_version, cuda_compiler, cuda_archs = sys.argv[1:]
root = Path(runtime_dir)
binary = root / "build/bin/llama-completion"
digest = hashlib.sha256()
with binary.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
manifest = {
    "repository": repository,
    "ref": ref,
    "commit": commit,
    "binary_sha256": digest.hexdigest(),
    "binary_path": str(binary),
    "device": device,
    "cuda_toolkit_version": cuda_version or None,
    "cuda_compiler": cuda_compiler or None,
    "cuda_architectures": cuda_archs or None,
    "built_at": datetime.now(timezone.utc).isoformat(),
}
target = root / "build/gemmagraph-runtime.json"
temporary = target.with_suffix(".json.tmp")
temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
temporary.replace(target)
print(f"官方 llama.cpp 构建完成：{binary}")
print(f"版本：{ref} ({commit})，设备：{device}")
PY
