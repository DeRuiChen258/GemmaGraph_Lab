"""Run the official llama.cpp completion program without an HTTP service."""

import asyncio
import json
import os
import re
import signal
import tempfile
import time
from pathlib import Path

from gemmagraph.errors import AppError
from gemmagraph.providers.local_model import file_sha256, inspect_gguf

UPSTREAM = "https://github.com/ggml-org/llama.cpp"
RUNTIME_REF = "v0.7.0"


class LlamaCppLocalProvider:
    def __init__(self, settings):
        self.settings = settings
        self.binary = settings.llama_cpp_dir / "build/bin/llama-completion"
        self.manifest = settings.llama_cpp_dir / "build/gemmagraph-runtime.json"

    def inspect(self):
        try:
            metadata = inspect_gguf(self.settings.model_path)
        except (OSError, ValueError, UnicodeError) as error:
            raise AppError("invalid_local_model", f"本地权重检查失败：{error}", 503) from error
        if metadata["architecture"] != "gemma4" or not metadata["embedded_chat_template"]:
            raise AppError("invalid_local_model", "需要带内置聊天模板的 Gemma 4 GGUF 权重", 503)
        if not isinstance(metadata["context_length"], int):
            raise AppError("invalid_local_model", "GGUF 缺少有效的上下文长度", 503)
        if self.settings.model_context_window > metadata["context_length"]:
            raise AppError("invalid_context_window", "配置的上下文超过本地模型支持的长度", 503)
        if self.settings.model_max_output_tokens >= self.settings.model_context_window:
            raise AppError("invalid_output_budget", "输出 token 上限必须小于上下文长度", 503)
        return metadata

    async def check(self):
        metadata = self.inspect()
        if not self.binary.is_file() or not os.access(self.binary, os.X_OK):
            raise AppError("local_runtime_missing",
                           "官方 llama.cpp 尚未构建；请运行 ./scripts/install-llama-cpp.sh --cuda", 503)
        try:
            manifest = json.loads(self.manifest.read_text())
            if (manifest.get("repository", "").removesuffix(".git") != UPSTREAM
                    or manifest.get("ref") != RUNTIME_REF
                    or not manifest.get("commit", "").startswith("620d222")
                    or manifest.get("binary_sha256") != file_sha256(self.binary)):
                raise ValueError("上游来源、版本或二进制哈希不匹配")
        except (OSError, ValueError, TypeError, AttributeError) as error:
            raise AppError("local_runtime_unverified",
                           "官方 runtime 构建记录无效；请重新运行 scripts/install-llama-cpp.sh", 503) from error
        if self.settings.model_gpu_layers > 0 and (
            manifest.get("device") != "cuda" or manifest.get("cuda_toolkit_version") != "13.4"
        ):
            raise AppError("cuda_runtime_required", "当前配置需要官方上游源码与 CUDA 13.4 的构建产物", 503)
        return {"reachable": True, "provider": "llama_cpp_local", "transport": "subprocess",
                "model_id": self.settings.model_id, "model_match": True, "metadata": metadata,
                "runtime": {"repository": UPSTREAM, "ref": RUNTIME_REF, "commit": manifest["commit"],
                            "device": manifest.get("device"), "binary_sha256": manifest["binary_sha256"],
                            "cuda_toolkit_version": manifest.get("cuda_toolkit_version")},
                "capabilities": {"generation": "not_probed", "streaming": "not_enabled",
                                 "json_schema": "not_probed", "token_count": "runtime_usage_or_unknown",
                                 "seed": "supported"}}

    def command(self, prompt_file: Path, seed: int | None):
        command = [str(self.binary), "--model", str(self.settings.model_path),
                "--file", str(prompt_file), "--conversation", "--jinja", "--single-turn",
                "--simple-io", "--no-display-prompt", "--no-escape", "--offline",
                "--no-warmup", "--no-context-shift", "--reasoning", "off", "--color", "off",
                "--log-colors", "off", "--ctx-size", str(self.settings.model_context_window),
                "--n-predict", str(self.settings.model_max_output_tokens),
                "--gpu-layers", str(self.settings.model_gpu_layers),
                "--threads", str(self.settings.model_threads), "--temp", "0.1",
                "--seed", str(seed if seed is not None else 42)]
        if self.settings.model_gpu_layers > 0:
            command.extend(["--device", "CUDA0", "--fit", "off"])
        return command

    async def generate(self, prompt: str, seed: int | None = None) -> dict:
        await self.check()
        if not prompt.strip():
            raise AppError("empty_prompt", "本地模型提示词不能为空")
        directory = self.settings.data_dir / "model-tmp"
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.TemporaryDirectory(prefix="inference-", dir=directory) as temporary:
            prompt_file = Path(temporary) / "prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")
            prompt_file.chmod(0o600)
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith(("LLAMA_ARG_", "MODEL_API_", "HF_TOKEN", "GOOGLE_API_KEY",
                                          "GEMINI_API_KEY", "OPENAI_API_KEY"))}
            env["LLAMA_CACHE"] = str(self.settings.data_dir / "llama-cache")
            started = time.monotonic()
            try:
                process = await asyncio.create_subprocess_exec(
                    *self.command(prompt_file, seed), cwd=temporary, env=env,
                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, start_new_session=True)
            except OSError as error:
                raise AppError("local_runtime_start_failed", f"无法启动官方推理程序：{error}", 503) from error
            communication = asyncio.create_task(process.communicate())
            try:
                stdout, stderr = await asyncio.wait_for(asyncio.shield(communication),
                                                        timeout=self.settings.model_timeout_seconds)
            except asyncio.TimeoutError as error:
                await self._stop(process, communication)
                raise AppError("provider_timeout", "本地 Gemma 4 推理超时，推理进程已停止", 504) from error
            except asyncio.CancelledError:
                await asyncio.shield(self._stop(process, communication))
                raise
            if process.returncode:
                detail = stderr.decode(errors="replace")[-1600:]
                raise AppError("local_inference_failed",
                               f"llama.cpp 退出码 {process.returncode}：{detail}", 502)
            text = stdout.decode("utf-8", errors="replace").strip()
            text = text.removesuffix("[end of text]").strip()
            if not text:
                raise AppError("empty_model_output", "本地模型未生成内容", 502)
            diagnostics = stderr.decode(errors="replace")
            prompt_count = re.search(r"prompt eval time\s*=.*?/\s*(\d+)\s*tokens", diagnostics)
            output_count = re.search(r"(?<!prompt )eval time\s*=.*?/\s*(\d+)\s*runs", diagnostics)
            # Eval runs exclude the first sampled token; they are not completion usage.
            return {"text": text, "input_tokens": int(prompt_count[1]) if prompt_count else None,
                    "output_tokens": None, "thought_tokens": None,
                    "runtime_eval_runs": int(output_count[1]) if output_count else None,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "request_id": None, "provider": "llama_cpp_local"}

    @staticmethod
    async def _stop(process, communication):
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            await asyncio.wait_for(asyncio.shield(communication), timeout=3)
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await communication
