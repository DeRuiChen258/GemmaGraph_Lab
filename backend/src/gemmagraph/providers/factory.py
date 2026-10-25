from gemmagraph.errors import AppError
from gemmagraph.providers.compatible_http import CompatibleHTTPProvider
from gemmagraph.providers.google_genai import GoogleGenAIProvider
from gemmagraph.providers.llama_cpp_local import LlamaCppLocalProvider


def provider_factory(settings):
    if settings.model_provider == "llama_cpp_local":
        return LlamaCppLocalProvider(settings)
    if settings.model_provider == "google_genai":
        if not settings.model_base_url or not settings.model_id or not settings.model_api_key:
            raise AppError("provider_not_configured", "请配置 MODEL_BASE_URL、MODEL_ID 与 MODEL_API_KEY", 503)
        return GoogleGenAIProvider(settings)
    if settings.model_provider != "compatible_http":
        raise AppError("unsupported_provider", "不支持的模型 provider", 503)
    if not settings.model_base_url or not settings.model_id:
        raise AppError("provider_not_configured", "请配置 MODEL_BASE_URL 与 MODEL_ID", 503)
    return CompatibleHTTPProvider(settings)
