"""Runtime protocol/lifecycle tests, using executable fixtures, not model inference."""

import asyncio
import json
import os
import struct
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from gemmagraph.errors import AppError
from gemmagraph.providers.llama_cpp_local import LlamaCppLocalProvider
from gemmagraph.providers.local_model import file_sha256, inspect_gguf
from gemmagraph.settings import Settings


def metadata_file(path, architecture="gemma4", template=True):
    """Metadata-only fixture, intentionally not a loadable model."""
    def string(value):
        raw = value.encode()
        return struct.pack("<Q", len(raw)) + raw
    values = [("general.architecture", 8, string(architecture)),
              ("general.file_type", 4, struct.pack("<I", 2)),
              ("gemma4.context_length", 4, struct.pack("<I", 131072))]
    if template:
        values.append(("tokenizer.chat_template", 8, string("fixture template")))
    path.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 1, len(values))
                     + b"".join(string(k) + struct.pack("<I", t) + v for k, t, v in values))


@pytest.fixture
def local_provider(tmp_path):
    model = tmp_path / "metadata-only.gguf"
    metadata_file(model)
    settings = Settings(_env_file=None, model_path=model, llama_cpp_dir=tmp_path / "runtime",
                        data_dir=tmp_path / "data", model_gpu_layers=0)
    provider = LlamaCppLocalProvider(settings)
    provider.binary.parent.mkdir(parents=True)
    return provider


def executable_fixture(provider, source):
    provider.binary.write_text(f"#!{sys.executable}\n" + source)
    provider.binary.chmod(0o755)


def test_gguf_metadata_and_truncation(local_provider, tmp_path):
    metadata = inspect_gguf(local_provider.settings.model_path)
    assert metadata["architecture"] == "gemma4" and metadata["embedded_chat_template"]
    invalid = tmp_path / "truncated.gguf"
    invalid.write_bytes(b"GGUF\x03")
    with pytest.raises(ValueError, match="截断"):
        inspect_gguf(invalid)


@pytest.mark.parametrize("architecture,template", [("llama", True), ("gemma4", False)])
def test_rejects_incorrect_model(local_provider, architecture, template):
    metadata_file(local_provider.settings.model_path, architecture, template)
    with pytest.raises(AppError) as error:
        local_provider.inspect()
    assert error.value.code == "invalid_local_model"


async def test_missing_runtime_never_falls_back_to_http(local_provider):
    with pytest.raises(AppError) as error:
        await local_provider.check()
    assert error.value.code == "local_runtime_missing"


async def test_rejects_fork_provenance(local_provider):
    executable_fixture(local_provider, "print('not a model')\n")
    local_provider.manifest.write_text(json.dumps({"repository": "https://github.com/PrismML-Eng/llama.cpp",
                                                "ref": "v0.7.0", "commit": "620d222fixture",
                                                "binary_sha256": file_sha256(local_provider.binary)}))
    with pytest.raises(AppError) as error:
        await local_provider.check()
    assert error.value.code == "local_runtime_unverified"


async def test_gpu_configuration_requires_cuda_134_build(local_provider):
    executable_fixture(local_provider, "print('not a model')\n")
    local_provider.settings.model_gpu_layers = 999
    local_provider.manifest.write_text(json.dumps({"repository": "https://github.com/ggml-org/llama.cpp",
                                                "ref": "v0.7.0", "commit": "620d222fixture",
                                                "binary_sha256": file_sha256(local_provider.binary),
                                                "device": "cuda", "cuda_toolkit_version": "13.3"}))
    with pytest.raises(AppError) as error:
        await local_provider.check()
    assert error.value.code == "cuda_runtime_required"
    command = local_provider.command(Path("prompt.txt"), 42)
    assert command[command.index("--device") + 1] == "CUDA0"
    assert command[command.index("--fit") + 1] == "off"


async def test_stdio_preserves_prompt_without_shell_and_cleans_temp(local_provider, monkeypatch):
    monkeypatch.setattr(local_provider, "check", AsyncMock(return_value={"protocol_fixture": True}))
    executable_fixture(local_provider, """import pathlib, sys
prompt = pathlib.Path(sys.argv[sys.argv.index('--file') + 1]).read_text()
print(prompt + ' [end of text]')
print('llama_perf_context_print: prompt eval time = 2.0 ms / 7 tokens', file=sys.stderr)
print('llama_perf_context_print: eval time = 3.0 ms / 2 runs', file=sys.stderr)
""")
    prompt = "literal \\n and $(touch forbidden-file) `echo hi`\n中文"
    result = await local_provider.generate(prompt, seed=7)
    assert result["text"] == prompt
    assert result["input_tokens"] == 7
    assert result["output_tokens"] is None and result["runtime_eval_runs"] == 2
    assert not list((local_provider.settings.data_dir / "model-tmp").iterdir())
    assert not (Path.cwd() / "forbidden-file").exists()


@pytest.mark.parametrize("cancel", [False, True])
async def test_timeout_and_cancel_stop_subprocess(local_provider, monkeypatch, tmp_path, cancel):
    monkeypatch.setattr(local_provider, "check", AsyncMock(return_value={"protocol_fixture": True}))
    pid_file = tmp_path / "child.pid"
    executable_fixture(local_provider, f"""import os, pathlib, time
pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))
time.sleep(60)
""")
    local_provider.settings.model_timeout_seconds = 2 if cancel else .2
    task = asyncio.create_task(local_provider.generate("protocol fixture only"))
    if cancel:
        for _ in range(100):
            if pid_file.exists():
                break
            await asyncio.sleep(.01)
        assert pid_file.exists()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        with pytest.raises(AppError) as error:
            await task
        assert error.value.code == "provider_timeout"
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)
    assert not list((local_provider.settings.data_dir / "model-tmp").iterdir())
