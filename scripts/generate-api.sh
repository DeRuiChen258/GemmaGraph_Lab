#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
uv run --project backend python -c 'import json; from gemmagraph.main import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))' > backend/openapi.json
pnpm --dir frontend generate:api
