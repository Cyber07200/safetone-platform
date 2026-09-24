"""AI Provider Layer: adapters and router (no real network calls)."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.core.errors import LiveModeUnavailable, ProviderError
from app.services.ai.base import Message
from app.services.ai.router import AIRouter
from tests.helpers import (GigaChatProvider, OpenAICompatibleProvider, YandexGPTProvider, body, openai_response,
                           settings, wire)

MSG = [Message("system", "s"), Message("user", "Привет")]


def run(coro):
    return asyncio.run(coro)


# ---- adapters ----------------------------------------------------------------
def test_yandex_request_format_and_parsing():
    seen = {}

    def handler(req: httpx.Request):
        seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["Authorization"], body(req)
        return httpx.Response(200, json={"result": {"alternatives": [{"message": {"role": "assistant", "text": "Ответ"},
                                                                     "status": "ALTERNATIVE_STATUS_FINAL"}],
                                                    "usage": {"inputTextTokens": "10", "completionTokens": "5",
                                                              "totalTokens": "15"}, "modelVersion": "23.10"}})
    p = wire(YandexGPTProvider(settings(yandex_api_key="AQVNtestkey1234567890", yandex_folder_id="b1gfolder",
                                        yandex_cost_per_1k_tokens=0.4)), handler)
    res = run(p.complete(MSG, max_tokens=100))
    assert seen["url"] == "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    assert seen["auth"] == "Api-Key AQVNtestkey1234567890"
    assert seen["body"]["modelUri"] == "gpt://b1gfolder/yandexgpt-lite/latest"
    assert seen["body"]["messages"][1] == {"role": "user", "text": "Привет"}
    assert seen["body"]["completionOptions"]["maxTokens"] == "100"
    assert res.text == "Ответ" and res.usage.total_tokens == 15
    assert res.cost_estimate == pytest.approx(0.006)


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
        return openai_response("Здравствуйте", model="GigaChat")
    p = wire(GigaChatProvider(settings(gigachat_auth_key="Z2lnYWtleQ==")), handler)
    assert run(p.complete(MSG)).text == "Здравствуйте"
    run(p.complete(MSG))  # token cached
    assert sum("oauth" in c for c in calls) == 1
    assert calls[-1] == "https://api.giga.chat/v1/chat/completions"


def test_gigachat_builds_auth_key_from_client_credentials():
    p = GigaChatProvider(settings(gigachat_client_id="id", gigachat_client_secret="secret"))
    assert p.is_configured() and p._auth_key() == "aWQ6c2VjcmV0"


def test_openai_compatible_json_mode():
    def handler(req):
        assert body(req)["response_format"] == {"type": "json_object"}
        return openai_response('{"ok": true}')
    p = wire(OpenAICompatibleProvider(settings(openai_api_key="k" * 12, openai_base_url="https://x.test/v1",
                                               openai_model="m")), handler)
    assert run(p.complete(MSG, json_mode=True)).text == '{"ok": true}'


@pytest.mark.parametrize("status,retryable,code", [(401, False, "PROVIDER_AUTH_FAILED"),
                                                   (429, True, "PROVIDER_RATE_LIMITED"),
                                                   (503, True, "PROVIDER_HTTP_ERROR")])
def test_http_errors_are_classified(status, retryable, code):
    p = wire(OpenAICompatibleProvider(settings(openai_api_key="k" * 12, openai_base_url="https://x.test/v1",
                                               openai_model="m")), lambda r: httpx.Response(status, text="secret body"))
    with pytest.raises(ProviderError) as e:
        run(p.complete(MSG))
    assert e.value.retryable is retryable and e.value.code == code
    assert "secret body" not in e.value.message


def test_timeout_is_retryable_error():
    def handler(req):
        raise httpx.ReadTimeout("slow", request=req)
    p = wire(OpenAICompatibleProvider(settings(openai_api_key="k" * 12, openai_base_url="https://x.test/v1",
                                               openai_model="m")), handler)
    with pytest.raises(ProviderError) as e:
        run(p.complete(MSG))
    assert e.value.code == "PROVIDER_TIMEOUT" and e.value.retryable


def test_unconfigured_provider_reports_missing_config():
    p = YandexGPTProvider(settings())
    assert not p.is_configured()
    assert "YANDEX_API_KEY или YANDEX_IAM_TOKEN" in p.missing_config()


# ---- router ------------------------------------------------------------------------
def _three(handlers: dict, **cfg):
    s = settings(yandex_api_key="AQVNkey1234567890", yandex_folder_id="f", gigachat_auth_key="a2V5",
                 openai_api_key="k" * 12, openai_base_url="https://x.test/v1", openai_model="m", **cfg)
    ps = {"yandex": YandexGPTProvider(s), "gigachat": GigaChatProvider(s), "openai": OpenAICompatibleProvider(s)}
    for name, h in handlers.items():
        wire(ps[name], h)
    return AIRouter(s, ps)


def _yandex_ok(req):
    return httpx.Response(200, json={"result": {"alternatives": [{"message": {"text": "yandex"}}], "usage": {}}})


def test_router_raises_when_nothing_configured():
    r = AIRouter(settings())
    assert not r.live_available()
    with pytest.raises(LiveModeUnavailable):
        run(r.complete("generation", MSG))


def test_router_manual_choice_is_used_first():
    calls = []
    r = _three({"yandex": lambda q: (calls.append("y"), _yandex_ok(q))[1],
                "openai": lambda q: (calls.append("o"), openai_response("o"))[1]})
    res = run(r.complete("generation", MSG, preference="yandex"))
    assert res.result.provider == "yandex" and calls == ["y"]
    assert res.attempts[0].selection_reason == "выбран вручную в настройках"


def test_router_manual_choice_of_unconfigured_provider_fails_clearly():
    r = AIRouter(settings(openai_api_key="k" * 12, openai_base_url="https://x.test/v1", openai_model="m"))
    with pytest.raises(LiveModeUnavailable):
        r.rank("generation", "gigachat")


def test_router_quality_policy_prefers_higher_tier_and_economy_prefers_cheaper():
    r = _three({}, yandex_cost_per_1k_tokens=0.2, openai_cost_per_1k_tokens=2.0, gigachat_cost_per_1k_tokens=0.5)
    assert r.rank("generation", "auto", "quality")[0][0].name == "openai"
    assert r.rank("generation", "auto", "economy")[0][0].name == "yandex"


def test_router_falls_back_sequentially_and_logs_attempts():
    calls = []

    def bad(req):
        calls.append("o")
        return httpx.Response(500)

    def good(req):
        calls.append("y")
        return _yandex_ok(req)
    s = settings(yandex_api_key="AQVNkey1234567890", yandex_folder_id="f", openai_api_key="k" * 12,
                 openai_base_url="https://x.test/v1", openai_model="m", ai_max_retries=1)
    r = AIRouter(s, {"openai": wire(OpenAICompatibleProvider(s), bad), "yandex": wire(YandexGPTProvider(s), good)})
    res = run(r.complete("generation", MSG, quality="quality"))
    assert res.result.provider == "yandex"
    assert calls == ["o", "o", "y"]                      # 1 retry, then fallback, never parallel
    assert [a.ok for a in res.attempts] == [False, False, True]


def test_non_retryable_error_is_not_retried():
    calls = []
    s = settings(openai_api_key="k" * 12, openai_base_url="https://x.test/v1", openai_model="m", ai_max_retries=3)
    r = AIRouter(s, {"openai": wire(OpenAICompatibleProvider(s), lambda q: (calls.append(1), httpx.Response(401))[1])})
    with pytest.raises(ProviderError) as e:
        run(r.complete("generation", MSG))
    assert len(calls) == 1 and e.value.code == "ALL_PROVIDERS_FAILED"
    assert len(e.value.attempts) == 1  # type: ignore[attr-defined]


def test_circuit_breaker_skips_failing_provider():
    s = settings(yandex_api_key="AQVNkey1234567890", yandex_folder_id="f", openai_api_key="k" * 12,
                 openai_base_url="https://x.test/v1", openai_model="m", ai_max_retries=0)
    r = AIRouter(s, {"openai": wire(OpenAICompatibleProvider(s), lambda q: httpx.Response(503)),
                     "yandex": wire(YandexGPTProvider(s), _yandex_ok)})
    for _ in range(3):
        run(r.complete("generation", MSG, quality="quality"))
    assert not r.health["openai"].available()
    assert [p.name for p, _ in r.rank("generation", "auto", "quality")] == ["yandex"]
    assert next(x for x in r.status() if x["name"] == "openai")["status"] == "unavailable"


def test_status_never_exposes_secrets():
    r = _three({})
    dump = str(r.status())
    assert "AQVNkey1234567890" not in dump and "k" * 12 not in dump and "a2V5" not in dump
