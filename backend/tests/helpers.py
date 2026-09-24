"""Test helpers: providers wired to httpx.MockTransport (no real network)."""
from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from app.core.config import Settings
from app.services.ai.providers import GigaChatProvider, OpenAICompatibleProvider, YandexGPTProvider
from app.services.ai.router import AIRouter


def wire(provider, handler: Callable[[httpx.Request], httpx.Response]):
    provider._client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[method-assign]
    return provider


def settings(**kw) -> Settings:
    base = dict(_env_file=None, yandex_api_key=None, gigachat_auth_key=None, openai_api_key=None,
                ai_max_retries=1)
    base.update(kw)
    return Settings(**base)


def openai_response(text: str, model: str = "test-model", tokens: int = 42) -> httpx.Response:
    return httpx.Response(200, json={"model": model, "choices": [{"message": {"content": text}}],
                                     "usage": {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": tokens}})


def openai_router(handler, **kw) -> tuple[AIRouter, OpenAICompatibleProvider]:
    s = settings(openai_api_key="sk-test-key-000000", openai_base_url="https://llm.test/v1",
                 openai_model="test-model", **kw)
    p = wire(OpenAICompatibleProvider(s), handler)
    return AIRouter(s, {"openai": p}), p


def body(req: httpx.Request) -> dict:
    return json.loads(req.content.decode())


__all__ = ["wire", "settings", "openai_response", "openai_router", "body", "YandexGPTProvider", "GigaChatProvider",
           "OpenAICompatibleProvider"]
