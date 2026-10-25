#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

command -v uv >/dev/null || { echo "需要安装 uv。" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "需要安装 pnpm 11。" >&2; exit 1; }

UV_CACHE_DIR="$ROOT/.uv-cache" uv sync --project backend --group dev
CI=true pnpm --dir frontend install --store-dir "$ROOT/.pnpm-store"
