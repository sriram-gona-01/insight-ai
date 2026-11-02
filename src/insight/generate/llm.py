"""LLM clients with one interface: local Ollama, or any OpenAI-compatible server (vLLM)."""

import base64
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import httpx

from insight.config import Settings

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    pass


@dataclass(frozen=True)
class GenerationOptions:
    temperature: float
    seed: int
    max_tokens: int
    context_tokens: int


class LLMClient(Protocol):
    model: str

    def generate(self, system: str, user: str, images: list[bytes]) -> str: ...

    def is_reachable(self) -> bool: ...


class _HttpClient:
    """Shared HTTP behaviour: timeouts, retries with exponential backoff, clear errors."""

    def __init__(
        self,
        base_url: str,
        timeout: float,
        max_retries: int,
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=timeout, headers=headers, transport=transport
        )
        self._max_retries = max_retries
        self._sleep = sleep

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        last_error = ""
        for attempt in range(self._max_retries + 1):
            if attempt:
                self._sleep(2 ** (attempt - 1))
            try:
                response = self._http.post(path, json=payload)
            except httpx.TransportError as e:
                last_error = f"{type(e).__name__}: {e}"
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                continue
            if response.status_code >= 400:
                raise LLMError(
                    f"{self._http.base_url}{path} returned HTTP {response.status_code}: "
                    f"{response.text[:300]}"
                )
            return response.json()
        raise LLMError(
            f"{self._http.base_url}{path} failed after {self._max_retries + 1} attempts: "
            f"{last_error}"
        )

    def _get_ok(self, path: str) -> httpx.Response | None:
        try:
            response = self._http.get(path, timeout=5)
        except httpx.TransportError:
            return None
        return response if response.status_code == 200 else None


class OllamaClient(_HttpClient):
    def __init__(
        self, base_url: str, model: str, options: GenerationOptions, **http_kwargs: Any
    ) -> None:
        super().__init__(base_url, **http_kwargs)
        self.model = model
        self._options = options

    def generate(self, system: str, user: str, images: list[bytes]) -> str:
        message: dict[str, Any] = {"role": "user", "content": user}
        if images:
            message["images"] = [base64.b64encode(image).decode() for image in images]
        data = self._post(
            "/api/chat",
            {
                "model": self.model,
                "stream": False,
                "think": False,
                "messages": [{"role": "system", "content": system}, message],
                "options": {
                    "temperature": self._options.temperature,
                    "seed": self._options.seed,
                    "num_predict": self._options.max_tokens,
                    "num_ctx": self._options.context_tokens,
                },
            },
        )
        return data["message"]["content"].strip()

    def is_reachable(self) -> bool:
        response = self._get_ok("/api/tags")
        if response is None:
            return False
        return any(m.get("name") == self.model for m in response.json().get("models", []))


class OpenAICompatClient(_HttpClient):
    """`base_url` includes the version prefix, for example http://host:8000/v1."""

    def __init__(
        self,
        base_url: str,
        model: str,
        options: GenerationOptions,
        api_key: str = "",
        **http_kwargs: Any,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        super().__init__(base_url, headers=headers, **http_kwargs)
        self.model = model
        self._options = options

    def generate(self, system: str, user: str, images: list[bytes]) -> str:
        content: list[dict[str, Any]] = [{"type": "text", "text": user}]
        for image in images:
            encoded = base64.b64encode(image).decode()
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
            )
        data = self._post(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": content},
                ],
                "temperature": self._options.temperature,
                "seed": self._options.seed,
                "max_tokens": self._options.max_tokens,
            },
        )
        return data["choices"][0]["message"]["content"].strip()

    def is_reachable(self) -> bool:
        return self._get_ok("/models") is not None


def build_llm_client(settings: Settings) -> LLMClient:
    options = GenerationOptions(
        settings.llm_temperature,
        settings.llm_seed,
        settings.llm_max_tokens,
        settings.llm_context_tokens,
    )
    http = {
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }
    if settings.llm_backend == "ollama":
        return OllamaClient(settings.ollama_url, settings.llm_model, options, **http)
    if settings.llm_backend == "openai_compat":
        return OpenAICompatClient(
            settings.llm_base_url, settings.llm_model, options, settings.llm_api_key, **http
        )
    raise ValueError(f"Unknown LLM_BACKEND '{settings.llm_backend}'")


@lru_cache(maxsize=1)
def get_llm_client(settings: Settings) -> LLMClient:
    return build_llm_client(settings)
