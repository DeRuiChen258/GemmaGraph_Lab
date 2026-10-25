#!/usr/bin/env python3
"""Inspect or run the configured local Gemma 4 with official llama.cpp."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))

async def main():
    from gemmagraph.errors import AppError
    from gemmagraph.providers.llama_cpp_local import LlamaCppLocalProvider
    from gemmagraph.providers.local_model import file_sha256
    from gemmagraph.settings import Settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="只检查文件与 runtime，不生成文本")
    parser.add_argument("--sha256", action="store_true", help="同时计算整个权重的 SHA256")
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()
    if not 1 <= args.max_tokens <= 4096:
        parser.error("--max-tokens 必须在 1..4096 内")
    settings = Settings()
    if settings.model_provider != "llama_cpp_local":
        print("本命令仅接受 MODEL_PROVIDER=llama_cpp_local。", file=sys.stderr)
        return 2
    settings = settings.model_copy(update={"model_max_output_tokens": args.max_tokens})
    provider = LlamaCppLocalProvider(settings)
    report = {"model_id": settings.model_id, "transport": "subprocess", "generated": False}
    try:
        report["metadata"] = provider.inspect()
        if args.sha256:
            report["model_sha256"] = file_sha256(settings.model_path)
        report["check"] = await provider.check()
        if not args.check_only:
            report["generation"] = await provider.generate("用一句中文介绍你自己。", seed=42)
            report["generated"] = True
    except (AppError, OSError, ValueError) as error:
        report["error"] = {"code": getattr(error, "code", "local_check_failed"), "message": str(error)}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
