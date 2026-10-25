#!/usr/bin/env bash
# Run on the host terminal with GPU, Docker and download access.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
REPORT_DIR="$ROOT/.data/validation/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$REPORT_DIR"
exec > >(tee "$REPORT_DIR/host-check.log") 2>&1
echo "验证记录：$REPORT_DIR"
./scripts/cuda-check.sh
./install.sh
./scripts/install-llama-cpp.sh --cuda
uv run --project backend --group dev pytest -c backend/pyproject.toml backend/tests
pnpm --dir frontend build
uv run --project backend python scripts/model-smoke.py --check-only --sha256 > "$REPORT_DIR/model-check.json"
uv run --project backend python scripts/model-smoke.py --max-tokens 128 > "$REPORT_DIR/model-generation.json"
docker build -t gemmagraph-sandbox:0.1 infra/sandbox
echo "CUDA 内核、依赖、工程回归、前端构建、实际模型生成和沙箱镜像构建完成。"
echo "模型回复与检查结果保存在：$REPORT_DIR"
echo "启动工作台：./scripts/dev.sh"
