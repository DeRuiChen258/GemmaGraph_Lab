from urllib.parse import urlsplit, urlunsplit

import httpx

from gemmagraph.errors import AppError


class CompatibleHTTPProvider:
    def __init__(self, settings):
        self.settings = settings
        parts = urlsplit(settings.model_base_url.rstrip("/"))
        if parts.scheme not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
            raise AppError("invalid_model_url", "MODEL_BASE_URL 必须是有效 HTTP(S) 地址且不能含凭证")
        self.base_url = urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))
        self.headers = {"Authorization": f"Bearer {settings.model_api_key}"} if settings.model_api_key else {}

    async def check(self):
        async with httpx.AsyncClient(timeout=min(self.settings.model_timeout_seconds, 10)) as client:
            try:
                response = await client.get(f"{self.base_url}/models", headers=self.headers)
                response.raise_for_status()
                body = response.json()
            except (httpx.HTTPError, ValueError) as e:
                raise AppError("provider_unavailable", f"模型服务连接检查失败：{type(e).__name__}", 502) from e
        ids = [x.get("id") for x in body.get("data", [])]
        return {"reachable": True, "model_id": self.settings.model_id,
                "available_models": ids[:50], "model_match": self.settings.model_id in ids,
                "capabilities": {"generation": "available", "streaming": "not_probed",
                                 "json_schema": "not_probed", "token_count": "unknown"}}

    async def generate(self, prompt: str, seed: int | None = None) -> dict:
        payload = {"model": self.settings.model_id, "messages": [{"role": "user", "content": prompt}],
                   "temperature": 0.1, "max_tokens": self.settings.model_max_output_tokens,
                   "stream": False}
        if seed is not None and getattr(self.settings, "model_supports_seed", False):
            payload["seed"] = seed
        async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds) as client:
            try:
                response = await client.post(f"{self.base_url}/chat/completions", headers=self.headers,
                                             json=payload)
                response.raise_for_status()
                body = response.json()
                text = body["choices"][0]["message"]["content"]
                if isinstance(text, list):
                    text = "".join(block.get("text", "") for block in text if isinstance(block, dict))
                if not isinstance(text, str) or not text:
                    raise ValueError("empty completion")
            except httpx.TimeoutException as e:
                raise AppError("provider_timeout", "模型服务请求超时；服务是否已完成计费未知", 504) from e
            except httpx.HTTPStatusError as e:
                raise AppError("provider_http_error", f"模型服务返回 HTTP {e.response.status_code}", 502) from e
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as e:
                raise AppError("provider_invalid_response", f"模型响应无效：{type(e).__name__}", 502) from e
        usage = body.get("usage") or {}
        return {"text": text, "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"), "request_id": body.get("id")}
