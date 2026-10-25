from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    model_provider: str = "llama_cpp_local"
    model_base_url: str = ""
    model_id: str = "gemma-4-E4B-QAT-Q4"
    model_path: Path = Path("/path/to/gemma-4-E4B_q4_0-it.gguf")
    llama_cpp_dir: Path = ROOT / ".runtime/llama.cpp"
    model_gpu_layers: int = Field(999, ge=0, le=999)
    model_threads: int = Field(8, ge=1, le=128)
    model_api_key: str = Field(default="", repr=False)
    model_revision: str = ""
    model_timeout_seconds: int = Field(600, ge=1, le=7200)
    model_context_window: int = Field(16384, ge=1024)
    model_max_output_tokens: int = Field(2048, ge=128)
    model_supports_seed: bool = False
    model_tokenizer_path: str = ""
    data_dir: Path = ROOT / ".data"
    sandbox_image: str = "gemmagraph-sandbox:0.1"
    allowed_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    api_host: str = "127.0.0.1"
    api_port: int = 8010

    @field_validator("data_dir", "model_path", "llama_cpp_dir", mode="before")
    @classmethod
    def resolve_data_dir(cls, value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else ROOT / path

    def model_status(self) -> dict:
        if self.model_provider == "llama_cpp_local":
            binary = self.llama_cpp_dir / "build/bin/llama-completion"
            manifest_exists = (self.llama_cpp_dir / "build/gemmagraph-runtime.json").is_file()
            return {
                "configured": self.model_path.is_file() and binary.is_file() and manifest_exists,
                "provider": self.model_provider, "base_url": "", "model_id": self.model_id,
                "model_path": str(self.model_path), "model_file_exists": self.model_path.is_file(),
                "runtime_path": str(binary), "runtime_exists": binary.is_file(),
                "runtime_manifest_exists": manifest_exists,
                "revision": self.model_revision or None, "key_configured": False,
                "transport": "subprocess", "device": "cpu" if self.model_gpu_layers == 0 else "gpu",
                "context_window": self.model_context_window,
                "max_output_tokens": self.model_max_output_tokens,
                "cuda_toolkit_version": "13.4" if self.model_gpu_layers > 0 else None,
            }
        u = urlsplit(self.model_base_url)
        safe_url = f"{u.scheme}://{u.hostname or ''}{':' + str(u.port) if u.port else ''}{u.path}"
        credentials_ready = self.model_provider != "google_genai" or bool(self.model_api_key)
        return {
            "provider": self.model_provider,
            "configured": bool(self.model_base_url and self.model_id and credentials_ready),
            "base_url": safe_url if self.model_base_url else "",
            "model_id": self.model_id,
            "revision": self.model_revision or None,
            "key_configured": bool(self.model_api_key),
        }

    def defaults(self) -> dict:
        return yaml.safe_load((ROOT / "configs/defaults.yaml").read_text())

    def profiles(self) -> dict:
        return yaml.safe_load((ROOT / "configs/test_profiles.yaml").read_text())
