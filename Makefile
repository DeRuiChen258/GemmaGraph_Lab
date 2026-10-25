.PHONY: install llama-cpp llama-cpp-cuda llama-cpp-cpu cuda-check verify-local dev build test api-schema model-check model-smoke

install:
	./install.sh

llama-cpp:
	./scripts/install-llama-cpp.sh --cuda

llama-cpp-cuda:
	./scripts/install-llama-cpp.sh --cuda

llama-cpp-cpu:
	./scripts/install-llama-cpp.sh --cpu

cuda-check:
	./scripts/cuda-check.sh

verify-local:
	./scripts/verify-local.sh

dev:
	./scripts/dev.sh

build:
	pnpm --dir frontend build

test:
	uv run --project backend --group dev pytest -c backend/pyproject.toml backend/tests

api-schema:
	./scripts/generate-api.sh

model-smoke:
	uv run --project backend python scripts/model-smoke.py

model-check:
	uv run --project backend python scripts/model-smoke.py --check-only
