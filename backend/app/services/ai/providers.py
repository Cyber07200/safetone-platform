"""GigaChat adapter — the only model SafeTone works with.

Endpoints and auth follow the public GigaChat API documentation (checked
2026-09): OAuth at GIGACHAT_OAUTH_URL (Basic <auth key>, RqUID, scope),
token lives 30 min; chat at {GIGACHAT_BASE_URL}/chat/completions.
TLS may require the Russian Trusted Root CA (set GIGACHAT_CA_BUNDLE).
URLs are configurable because endpoints move.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid

import httpx

from app.core.config import Settings
from app.core.errors import ProviderError
from .base import AIProvider, Message, ProviderProfile, Usage

log = logging.getLogger("safetone.ai.gigachat")


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
        msgs = [{"role": m.role, "content": m.content, **({"attachments": m.attachments} if m.attachments else {})}
                for m in messages]
        body = {"model": self.model, "messages": msgs, "temperature": temperature, "max_tokens": max_tokens,
                "stream": False}
        resp = await client.post(f"{self.s.gigachat_base_url.rstrip('/')}/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        if resp.status_code == 401:
            self._token = None
        self.raise_for_status(resp, self.name, self.label)
        return _parse_chat_completion(resp, self.name, self.label, self.model)


    async def transcribe(self, data: bytes, filename: str, mime: str) -> str:
        """Read the text of a photo or a scanned PDF: upload it to GigaChat (/files), ask the
        model to transcribe it, then delete the file from GigaChat whatever happens."""
        if not self.is_configured():
            raise ProviderError("Распознавание фото и сканов требует GigaChat: добавьте ключ в backend/.env.",
                                provider=self.name, code="PROVIDER_NOT_CONFIGURED")
        base = self.s.gigachat_base_url.rstrip("/")
        try:
            async with self._client() as client:
                token = await self._get_token(client)
                up = await client.post(f"{base}/files", files={"file": (filename, data, mime)},
                                       data={"purpose": "general"}, headers={"Authorization": f"Bearer {token}"})
                self.raise_for_status(up, self.name, self.label + " (загрузка файла)")
                file_id = up.json()["id"]
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.label}: превышено время загрузки файла", provider=self.name,
                                retryable=True, code="PROVIDER_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.label}: сетевая ошибка при загрузке файла", provider=self.name,
                                retryable=True, code="PROVIDER_NETWORK_ERROR") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError(f"{self.label}: неожиданный ответ на загрузку файла", provider=self.name,
                                code="PROVIDER_BAD_RESPONSE") from exc
        try:
            res = await self.complete([Message("user", TRANSCRIBE_PROMPT, attachments=[file_id])],
                                      temperature=0.0, max_tokens=4000)
        finally:
            await self._delete_file(file_id)
        return res.text

    async def _delete_file(self, file_id: str) -> None:
        try:
            async with self._client() as client:
                token = await self._get_token(client)
                resp = await client.post(f"{self.s.gigachat_base_url.rstrip('/')}/files/{file_id}/delete",
                                         headers={"Authorization": f"Bearer {token}"})
                if resp.status_code >= 400:
                    log.warning("GigaChat file delete failed: HTTP %s", resp.status_code)
        except (httpx.HTTPError, ProviderError) as exc:
            # The file stays in the GigaChat account; report it, don't fail the user's request.
            log.warning("GigaChat file delete failed: %s", type(exc).__name__)


TRANSCRIBE_PROMPT = (
    "Перепиши дословно весь текст документа из вложения: сохрани нумерацию пунктов, суммы, проценты, даты и "
    "сроки. Таблицы передай строками «ячейка — ячейка». Не добавляй комментариев и выводов. Если текста нет "
    "или он нечитаем, ответь ровно: ТЕКСТ НЕ РАСПОЗНАН."
)


def _int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _parse_chat_completion(resp: httpx.Response, name: str, label: str, model: str):
    try:
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        u = data.get("usage") or {}
        usage = Usage(_int(u.get("prompt_tokens")), _int(u.get("completion_tokens")), _int(u.get("total_tokens")))
        return text, usage, data.get("model") or model
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ProviderError(f"{label}: неожиданный формат ответа", provider=name, code="PROVIDER_BAD_RESPONSE") from exc


def build_providers(settings: Settings) -> dict[str, AIProvider]:
    return {p.name: p for p in (GigaChatProvider(settings),)}
