import base64
import json

import httpx
import pytest

from insight.config import Settings
from insight.generate.llm import (
    GenerationOptions,
    LLMError,
    OllamaClient,
    OpenAICompatClient,
    build_llm_client,
)

OPTIONS = GenerationOptions(temperature=0.0, seed=7, max_tokens=64, context_tokens=2048)


def ollama(handler, **kwargs) -> OllamaClient:
    return OllamaClient(
        "http://ollama",
        "vision",
        OPTIONS,
        timeout=1,
        max_retries=kwargs.pop("max_retries", 2),
        transport=httpx.MockTransport(handler),
        sleep=kwargs.pop("sleep", lambda _: None),
    )


def openai(handler, api_key: str = "secret") -> OpenAICompatClient:
    return OpenAICompatClient(
        "http://pod/v1",
        "vision",
        OPTIONS,
        api_key,
        timeout=1,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )


def test_ollama_request_format() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": " hello [S1] "}})

    assert ollama(handler).generate("sys", "user", [b"png"]) == "hello [S1]"
    body = seen["body"]
    assert seen["path"] == "/api/chat"
    assert body["stream"] is False
    assert body["messages"][0] == {"role": "system", "content": "sys"}
    assert body["messages"][1]["images"] == [base64.b64encode(b"png").decode()]
    assert body["options"] == {"temperature": 0.0, "seed": 7, "num_predict": 64, "num_ctx": 2048}


def test_ollama_omits_images_when_there_are_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "images" not in json.loads(request.content)["messages"][1]
        return httpx.Response(200, json={"message": {"content": "ok"}})

    assert ollama(handler).generate("s", "u", []) == "ok"


def test_retries_server_errors_with_backoff_then_succeeds() -> None:
    responses = [httpx.Response(503, text="busy"), httpx.Response(500, text="oops")]
    delays = []

    def handler(request: httpx.Request) -> httpx.Response:
        if responses:
            return responses.pop(0)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    assert ollama(handler, sleep=delays.append).generate("s", "u", []) == "ok"
    assert delays == [1, 2]


def test_retries_connection_errors_then_reports_them() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("refused")

    with pytest.raises(LLMError, match="failed after 3 attempts.*refused"):
        ollama(handler).generate("s", "u", [])
    assert len(calls) == 3


def test_client_errors_are_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, json={"error": "context too small"})

    with pytest.raises(LLMError, match="HTTP 400.*context too small"):
        ollama(handler).generate("s", "u", [])
    assert len(calls) == 1


def test_ollama_reachable_only_when_model_is_installed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "other"}]})

    assert ollama(handler).is_reachable() is False


def test_ollama_reachable_when_model_is_installed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "vision"}]})

    assert ollama(handler).is_reachable() is True


def test_ollama_unreachable_on_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    assert ollama(handler).is_reachable() is False


def test_openai_request_format() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    assert openai(handler).generate("sys", "user", [b"png"]) == "hi"
    assert seen["path"] == "/v1/chat/completions"
    assert seen["auth"] == "Bearer secret"
    body = seen["body"]
    assert (body["temperature"], body["seed"], body["max_tokens"]) == (0.0, 7, 64)
    text, image = body["messages"][1]["content"]
    assert text == {"type": "text", "text": "user"}
    encoded = base64.b64encode(b"png").decode()
    assert image["image_url"]["url"] == f"data:image/png;base64,{encoded}"


def test_openai_without_key_sends_no_auth_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"data": []})

    assert openai(handler, api_key="").is_reachable() is True


def test_backend_selection() -> None:
    assert isinstance(build_llm_client(Settings(_env_file=None)), OllamaClient)
    compat = Settings(_env_file=None, llm_backend="openai_compat", llm_base_url="http://pod/v1")
    assert isinstance(build_llm_client(compat), OpenAICompatClient)
    with pytest.raises(ValueError, match="Unknown LLM_BACKEND"):
        build_llm_client(Settings(_env_file=None, llm_backend="nope"))
