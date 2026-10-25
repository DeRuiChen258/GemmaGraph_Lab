from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from gemmagraph.errors import AppError


class GoogleGenAIProvider:
    """Native Gemini Developer API adapter for Gemma and Gemini model IDs."""

    def __init__(self, settings):
        self.settings = settings
        parts = urlsplit(settings.model_base_url.rstrip("/"))
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise AppError("invalid_model_url", "MODEL_BASE_URL 必须是有效 HTTP(S) 地址且不能含凭证")
        self.base_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        self.headers = {"x-goog-api-key": settings.model_api_key} if settings.model_api_key else {}
        self.model_id = settings.model_id.removeprefix("models/")

    @property
    def model_url(self):
        return f"{self.base_url}/models/{quote(self.model_id, safe='-_.')}:generateContent"

    async def check(self):
        model_id = quote(self.model_id, safe="-_.")
        async with httpx.AsyncClient(timeout=min(self.settings.model_timeout_seconds, 10)) as client:
            try:
                response = await client.get(f"{self.base_url}/models/{model_id}", headers=self.headers)
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as e:
                raise AppError("provider_unavailable", f"Gemma API 连接检查失败：{type(e).__name__}", 502) from e
        supports_generation = "generateContent" in body.get("supportedGenerationMethods", [])
        return {"reachable": True, "provider": "google_genai", "model_id": self.model_id,
                "available_models": [self.model_id] if supports_generation else [],
                "model_match": supports_generation,
                "capabilities": {"generation": "available", "streaming": "not_probed",
                                 "json_schema": "not_probed", "token_count": "provider_usage"}}

    async def generate(self, prompt: str, seed: int | None = None) -> dict:
        generation = {"temperature": 0.1, "maxOutputTokens": self.settings.model_max_output_tokens}
        if seed is not None and self.settings.model_supports_seed:
            generation["seed"] = seed
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                   "generationConfig": generation}
        async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds) as client:
            try:
                response = await client.post(self.model_url, headers=self.headers, json=payload)
                response.raise_for_status()
                body = response.json()
                candidates = body.get("candidates") or []
                parts = (candidates[0].get("content") or {}).get("parts") or []
                text = "".join(part.get("text", "") for part in parts
                               if isinstance(part, dict) and not part.get("thought"))
                if not text:
                    raise ValueError("empty completion")
            except httpx.TimeoutException as e:
                raise AppError("provider_timeout", "Gemma API 请求超时；服务是否已完成计费未知", 504) from e
            except httpx.HTTPStatusError as e:
                raise AppError("provider_http_error", f"Gemma API 返回 HTTP {e.response.status_code}", 502) from e
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
                raise AppError("provider_invalid_response", f"Gemma API 响应无效：{type(e).__name__}", 502) from e
        usage = body.get("usageMetadata") or {}
        return {"text": text, "input_tokens": usage.get("promptTokenCount"),
                "output_tokens": usage.get("candidatesTokenCount"),
                "thought_tokens": usage.get("thoughtsTokenCount"),
                "request_id": response.headers.get("x-request-id")}
