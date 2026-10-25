#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pids=()
stop_children() {
  trap - INT TERM EXIT
  for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${pids[@]}"; do wait "$pid" 2>/dev/null || true; done
}
trap stop_children INT TERM EXIT

uv run --project backend gemmagraph-api & pids+=("$!")
uv run --project backend gemmagraph-worker & pids+=("$!")
pnpm --dir frontend dev & pids+=("$!")
wait -n "${pids[@]}"
