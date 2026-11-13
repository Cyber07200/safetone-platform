"""Test helpers: GigaChat wired to httpx.MockTransport (no real network)."""
from __future__ import annotations

import json
from collections.abc import Callable

import httpx

from app.core.config import Settings
from app.services.ai.providers import GigaChatProvider
from app.services.ai.router import AIRouter

TEST_AUTH_KEY = "dGVzdC1pZDp0ZXN0LXNlY3JldA=="  # base64("test-id:test-secret"), not a real key


def wire(provider, handler: Callable[[httpx.Request], httpx.Response]):
    provider._client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))  # type: ignore[method-assign]
    return provider


def settings(**kw) -> Settings:
    base = dict(_env_file=None, gigachat_auth_key=None, ai_max_retries=1)
    base.update(kw)
    return Settings(**base)


def chat_response(text: str, model: str = "GigaChat-test", tokens: int = 42) -> httpx.Response:
    return httpx.Response(200, json={"model": model, "choices": [{"message": {"role": "assistant", "content": text}}],
                                     "usage": {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": tokens}})


def with_oauth(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[httpx.Request], httpx.Response]:
    """Answer the GigaChat OAuth request; pass chat requests to `handler`."""
    def h(req: httpx.Request) -> httpx.Response:
        if "oauth" in str(req.url):
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 4102444800000})
        return handler(req)
    return h


def gigachat_router(handler, **kw) -> tuple[AIRouter, GigaChatProvider]:
    s = settings(gigachat_auth_key=TEST_AUTH_KEY, gigachat_model="GigaChat-test", **kw)
    p = wire(GigaChatProvider(s), with_oauth(handler))
    return AIRouter(s, {"gigachat": p}), p


def body(req: httpx.Request) -> dict:
    return json.loads(req.content.decode())


__all__ = ["wire", "settings", "chat_response", "with_oauth", "gigachat_router", "body", "GigaChatProvider",
           "TEST_AUTH_KEY"]
