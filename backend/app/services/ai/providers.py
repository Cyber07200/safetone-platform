"""Vendor adapters.

Endpoints and auth follow the vendors' public documentation (checked
2026-09):
  * Yandex AI Studio: POST {YANDEX_BASE_URL}/completion, header
    `Authorization: Api-Key <key>` or `Bearer <IAM token>`, body
    {modelUri, completionOptions{stream,temperature,maxTokens}, messages[{role,text}]},
    response result.alternatives[].message.text, result.usage.
  * GigaChat: OAuth at GIGACHAT_OAUTH_URL (Basic <auth key>, RqUID, scope),
    token lives 30 min; chat at {GIGACHAT_BASE_URL}/chat/completions
    (OpenAI-like body). TLS may require the Russian Trusted Root CA
    (set GIGACHAT_CA_BUNDLE).
  * OpenAI-compatible: POST {OPENAI_BASE_URL}/chat/completions with Bearer key.
All URLs are configurable because vendors move endpoints.
"""
from __future__ import annotations

import asyncio
import base64
import time
import uuid

import httpx

from app.core.config import Settings
from app.core.errors import ProviderError
from .base import AIProvider, Message, ProviderProfile, Usage


class YandexGPTProvider(AIProvider):
    name = "yandex"
    label = "YandexGPT"

    def __init__(self, settings: Settings):
        super().__init__(timeout_s=settings.ai_request_timeout_s, profile=ProviderProfile(
            quality_tier=2, cost_per_1k_tokens=settings.yandex_cost_per_1k_tokens, supports_json=True))
        self.s = settings

    @property
    def model(self) -> str:
        if self.s.yandex_model_uri:
            return self.s.yandex_model_uri
        if self.s.yandex_folder_id:
            return f"gpt://{self.s.yandex_folder_id}/yandexgpt-lite/latest"
        return "yandexgpt-lite"

    def missing_config(self) -> list[str]:
        missing = []
        if not (self.s.yandex_api_key or self.s.yandex_iam_token):
            missing.append("YANDEX_API_KEY или YANDEX_IAM_TOKEN")
        if not (self.s.yandex_folder_id or self.s.yandex_model_uri):
            missing.append("YANDEX_FOLDER_ID или YANDEX_MODEL_URI")
        return missing

    def is_configured(self) -> bool:
        return not self.missing_config()

    def _auth_header(self) -> str:
        if self.s.yandex_api_key:
            return f"Api-Key {self.s.yandex_api_key.get_secret_value()}"
        return f"Bearer {self.s.yandex_iam_token.get_secret_value()}"  # type: ignore[union-attr]

    async def _complete(self, client, messages, *, temperature, max_tokens, json_mode):
        body = {
            "modelUri": self.model,
            "completionOptions": {"stream": False, "temperature": max(0.0, min(1.0, temperature)),
                                  "maxTokens": str(max_tokens)},
            "messages": [{"role": m.role, "text": m.content} for m in messages],
        }
        if json_mode:
            body["jsonObject"] = True
        headers = {"Authorization": self._auth_header(), "Content-Type": "application/json"}
        if self.s.yandex_folder_id:
            headers["x-folder-id"] = self.s.yandex_folder_id
        resp = await client.post(f"{self.s.yandex_base_url.rstrip('/')}/completion", json=body, headers=headers)
        self.raise_for_status(resp, self.name, self.label)
        try:
            data = resp.json()
            result = data.get("result", data)
            text = result["alternatives"][0]["message"]["text"]
            u = result.get("usage") or {}
            usage = Usage(_int(u.get("inputTextTokens")), _int(u.get("completionTokens")), _int(u.get("totalTokens")))
            return text, usage, result.get("modelVersion") and f"{self.model} ({result['modelVersion']})"
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderError(f"{self.label}: неожиданный формат ответа", provider=self.name,
                                code="PROVIDER_BAD_RESPONSE") from exc


class GigaChatProvider(AIProvider):
    name = "gigachat"
    label = "GigaChat"

    def __init__(self, settings: Settings):
        super().__init__(timeout_s=settings.ai_request_timeout_s, profile=ProviderProfile(
            quality_tier=2, cost_per_1k_tokens=settings.gigachat_cost_per_1k_tokens, supports_json=False))
        self.s = settings
        self._token: str | None = None
        self._token_exp: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def model(self) -> str:
        return self.s.gigachat_model

    def _auth_key(self) -> str | None:
        if self.s.gigachat_auth_key:
            return self.s.gigachat_auth_key.get_secret_value()
        if self.s.gigachat_client_id and self.s.gigachat_client_secret:
            raw = f"{self.s.gigachat_client_id}:{self.s.gigachat_client_secret.get_secret_value()}"
            return base64.b64encode(raw.encode()).decode()
        return None

    def missing_config(self) -> list[str]:
        return [] if self._auth_key() else ["GIGACHAT_AUTH_KEY или GIGACHAT_CLIENT_ID + GIGACHAT_CLIENT_SECRET"]

    def is_configured(self) -> bool:
        return not self.missing_config()

    def _client(self) -> httpx.AsyncClient:
        verify: bool | str = self.s.gigachat_ca_bundle or True
        return httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_s, connect=min(10.0, self.timeout_s)),
                                 verify=verify)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        async with self._lock:
            if self._token and time.time() < self._token_exp - 60:
                return self._token
            resp = await client.post(self.s.gigachat_oauth_url, data={"scope": self.s.gigachat_scope}, headers={
                "Authorization": f"Basic {self._auth_key()}", "RqUID": str(uuid.uuid4()),
                "Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
            self.raise_for_status(resp, self.name, self.label + " OAuth")
            try:
                data = resp.json()
                self._token = data["access_token"]
                exp = float(data.get("expires_at", 0))
                self._token_exp = exp / 1000 if exp > 1e11 else (exp or time.time() + 1500)
            except (KeyError, ValueError, TypeError) as exc:
                raise ProviderError(f"{self.label}: не удалось получить токен", provider=self.name,
                                    code="PROVIDER_AUTH_FAILED") from exc
            return self._token

    async def _complete(self, client, messages, *, temperature, max_tokens, json_mode):
        token = await self._get_token(client)
        body = {"model": self.model, "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": temperature, "max_tokens": max_tokens, "stream": False}
        resp = await client.post(f"{self.s.gigachat_base_url.rstrip('/')}/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        if resp.status_code == 401:
            self._token = None
        self.raise_for_status(resp, self.name, self.label)
        return _parse_openai_like(resp, self.name, self.label, self.model)


class OpenAICompatibleProvider(AIProvider):
    name = "openai"

    def __init__(self, settings: Settings):
        super().__init__(timeout_s=settings.ai_request_timeout_s, profile=ProviderProfile(
            quality_tier=3, cost_per_1k_tokens=settings.openai_cost_per_1k_tokens, supports_json=True))
        self.s = settings
        self.label = settings.openai_provider_label or "OpenAI-compatible"

    @property
    def model(self) -> str:
        return self.s.openai_model or "not-set"

    def missing_config(self) -> list[str]:
        m = []
        if not self.s.openai_api_key:
            m.append("OPENAI_API_KEY")
        if not self.s.openai_base_url:
            m.append("OPENAI_BASE_URL")
        if not self.s.openai_model:
            m.append("OPENAI_MODEL")
        return m

    def is_configured(self) -> bool:
        return not self.missing_config()

    async def _complete(self, client, messages, *, temperature, max_tokens, json_mode):
        body = {"model": self.model, "messages": [{"role": m.role, "content": m.content} for m in messages],
                "temperature": temperature, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        resp = await client.post(f"{self.s.openai_base_url.rstrip('/')}/chat/completions", json=body,  # type: ignore[union-attr]
                                 headers={"Authorization": f"Bearer {self.s.openai_api_key.get_secret_value()}"})  # type: ignore[union-attr]
        self.raise_for_status(resp, self.name, self.label)
        return _parse_openai_like(resp, self.name, self.label, self.model)


def _int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _parse_openai_like(resp: httpx.Response, name: str, label: str, model: str):
    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage") or {}
        usage = Usage(_int(u.get("prompt_tokens")), _int(u.get("completion_tokens")), _int(u.get("total_tokens")))
        return text, usage, data.get("model") or model
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError(f"{label}: неожиданный формат ответа", provider=name, code="PROVIDER_BAD_RESPONSE") from exc


def build_providers(settings: Settings) -> dict[str, AIProvider]:
    return {p.name: p for p in (YandexGPTProvider(settings), GigaChatProvider(settings),
                                OpenAICompatibleProvider(settings))}
