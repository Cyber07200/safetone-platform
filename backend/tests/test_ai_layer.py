"""AI layer: GigaChat adapter and router (no real network calls)."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.errors import LiveModeUnavailable, ProviderError
from app.services.ai.base import Message
from app.services.ai.router import AIRouter
from tests.helpers import TEST_AUTH_KEY, GigaChatProvider, body, chat_response, gigachat_router, settings, with_oauth, wire

MSG = [Message("system", "s"), Message("user", "Привет")]


def run(coro):
    return asyncio.run(coro)


def provider(handler, **kw) -> GigaChatProvider:
    return wire(GigaChatProvider(settings(gigachat_auth_key=TEST_AUTH_KEY, **kw)), with_oauth(handler))


# ---- adapter -----------------------------------------------------------------
def test_gigachat_oauth_then_chat():
    calls = []

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        if "oauth" in str(req.url):
            assert req.headers["Authorization"] == "Basic Z2lnYWtleQ=="
            assert "RqUID" in req.headers
            assert b"scope=GIGACHAT_API_PERS" in req.content
            return httpx.Response(200, json={"access_token": "tok", "expires_at": 4102444800000})
        assert req.headers["Authorization"] == "Bearer tok"
        assert body(req)["messages"][1] == {"role": "user", "content": "Привет"}
        return chat_response("Здравствуйте", model="GigaChat")
    p = wire(GigaChatProvider(settings(gigachat_auth_key="Z2lnYWtleQ==")), handler)
    assert run(p.complete(MSG)).text == "Здравствуйте"
    run(p.complete(MSG))  # token cached
    assert sum("oauth" in c for c in calls) == 1
    assert calls[-1] == "https://api.giga.chat/v1/chat/completions"


def test_gigachat_builds_auth_key_from_client_credentials():
    p = GigaChatProvider(settings(gigachat_client_id="id", gigachat_client_secret="secret"))
    assert p.is_configured() and p._auth_key() == "aWQ6c2VjcmV0"


def test_cost_estimate_uses_configured_tariff():
    res = run(provider(lambda r: chat_response("Ответ", tokens=15), gigachat_cost_per_1k_tokens=0.4).complete(MSG))
    assert res.text == "Ответ" and res.usage.total_tokens == 15
    assert res.cost_estimate == pytest.approx(0.006)


@pytest.mark.parametrize("status,retryable,code", [(401, False, "PROVIDER_AUTH_FAILED"),
                                                   (429, True, "PROVIDER_RATE_LIMITED"),
                                                   (503, True, "PROVIDER_HTTP_ERROR")])
def test_http_errors_are_classified(status, retryable, code):
    p = provider(lambda r: httpx.Response(status, text="secret body"))
    with pytest.raises(ProviderError) as e:
        run(p.complete(MSG))
    assert e.value.retryable is retryable and e.value.code == code
    assert "secret body" not in e.value.message


def test_timeout_is_retryable_error():
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)
    with pytest.raises(ProviderError) as e:
        run(provider(handler).complete(MSG))
    assert e.value.code == "PROVIDER_TIMEOUT" and e.value.retryable


def test_unconfigured_provider_reports_missing_config():
    p = GigaChatProvider(settings())
    assert not p.is_configured()
    assert "GIGACHAT_AUTH_KEY" in p.missing_config()[0]


# ---- router ------------------------------------------------------------------
def test_router_raises_when_nothing_configured():
    r = AIRouter(settings())
    assert not r.live_available()
    with pytest.raises(LiveModeUnavailable):
        run(r.complete("generation", MSG))


def test_router_unknown_provider_fails_clearly():
    r, _ = gigachat_router(lambda q: chat_response("ok"))
    with pytest.raises(LiveModeUnavailable):
        r.rank("generation", "other-model")


def test_router_retries_retryable_errors_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else chat_response("ok")
    r, _ = gigachat_router(handler, ai_max_retries=1)
    res = run(r.complete("generation", MSG))
    assert res.result.provider == "gigachat" and len(calls) == 2
    assert [a.ok for a in res.attempts] == [False, True]


def test_non_retryable_error_is_not_retried():
    calls = []
    r, _ = gigachat_router(lambda q: (calls.append(1), httpx.Response(403))[1], ai_max_retries=3)
    with pytest.raises(ProviderError) as e:
        run(r.complete("generation", MSG))
    assert len(calls) == 1 and e.value.code == "ALL_PROVIDERS_FAILED"
    assert len(e.value.attempts) == 1  # type: ignore[attr-defined]


def test_circuit_breaker_marks_failing_provider_unavailable():
    r, _ = gigachat_router(lambda q: httpx.Response(503), ai_max_retries=0)
    for _ in range(3):
        with pytest.raises(ProviderError):
            run(r.complete("generation", MSG))
    assert not r.health["gigachat"].available()
    assert r.status()[0]["status"] == "unavailable"


def test_status_never_exposes_secrets():
    r, _ = gigachat_router(lambda q: chat_response("ok"))
    assert TEST_AUTH_KEY not in str(r.status())
