"""AI Provider Layer — common interface for all LLM providers.

SafeTone does not host a model. Every provider is an adapter over a vendor
API; business logic depends only on `AIProvider`.
"""
from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Literal

import httpx

from app.core.errors import ProviderError

Role = Literal["system", "user", "assistant"]
Task = Literal["generation", "claim_extraction", "legal_verification", "linguistic_rewrite", "semantic_check"]


@dataclass
class Message:
    role: Role
    content: str
    attachments: list[str] | None = None  # provider file ids (GigaChat /files)


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class CompletionResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    usage: Usage = field(default_factory=Usage)
    cost_estimate: float | None = None  # in the currency of configured tariffs; None = unknown


@dataclass
class ProviderProfile:
    """Static routing hints. Cost is taken from configuration (the bank's
    actual contract); SafeTone does not invent vendor prices."""
    quality_tier: int = 2  # 1 economy .. 3 premium (configurable)
    cost_per_1k_tokens: float | None = None
    supports_json: bool = False
    tasks: tuple[str, ...] = ("generation", "claim_extraction", "legal_verification",
                              "linguistic_rewrite", "semantic_check")


class AIProvider(abc.ABC):
    name: str = "base"
    label: str = "Base"

    def __init__(self, *, timeout_s: float, profile: ProviderProfile):
        self.timeout_s = timeout_s
        self.profile = profile

    @abc.abstractmethod
    def is_configured(self) -> bool: ...

    @abc.abstractmethod
    def missing_config(self) -> list[str]: ...

    @property
    @abc.abstractmethod
    def model(self) -> str: ...

    @abc.abstractmethod
    async def _complete(self, client: httpx.AsyncClient, messages: list[Message], *, temperature: float,
                        max_tokens: int, json_mode: bool) -> tuple[str, Usage, str]:
        """Return (text, usage, model_version)."""

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_s, connect=min(10.0, self.timeout_s)))

    async def complete(self, messages: list[Message], *, temperature: float = 0.2, max_tokens: int = 800,
                       json_mode: bool = False) -> CompletionResult:
        if not self.is_configured():
            raise ProviderError(f"Провайдер {self.label} не настроен: " + ", ".join(self.missing_config()),
                                provider=self.name, code="PROVIDER_NOT_CONFIGURED")
        started = time.perf_counter()
        try:
            async with self._client() as client:
                text, usage, model_version = await self._complete(
                    client, messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode)
        except ProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise ProviderError(f"{self.label}: превышено время ожидания ответа", provider=self.name,
                                retryable=True, code="PROVIDER_TIMEOUT") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.label}: сетевая ошибка ({type(exc).__name__})", provider=self.name,
                                retryable=True, code="PROVIDER_NETWORK_ERROR") from exc
        if not text or not text.strip():
            raise ProviderError(f"{self.label}: пустой ответ модели", provider=self.name, retryable=True,
                                code="PROVIDER_EMPTY_RESPONSE")
        latency = int((time.perf_counter() - started) * 1000)
        cost = None
        if self.profile.cost_per_1k_tokens is not None and usage.total_tokens is not None:
            cost = round(usage.total_tokens / 1000 * self.profile.cost_per_1k_tokens, 4)
        return CompletionResult(text.strip(), self.name, model_version or self.model, latency, usage, cost)

    @staticmethod
    def raise_for_status(resp: httpx.Response, provider: str, label: str) -> None:
        if resp.status_code < 400:
            return
        retryable = resp.status_code in (408, 409, 425, 429) or resp.status_code >= 500
        code = {401: "PROVIDER_AUTH_FAILED", 403: "PROVIDER_FORBIDDEN", 429: "PROVIDER_RATE_LIMITED"}.get(
            resp.status_code, "PROVIDER_HTTP_ERROR")
        # Response bodies may echo request data; keep only a short, safe excerpt.
        raise ProviderError(f"{label}: HTTP {resp.status_code}", provider=provider, retryable=retryable,
                            http_status=resp.status_code, code=code)

    def describe(self) -> dict:
        return {
            "name": self.name,
            "label": self.label,
            "model": self.model if self.is_configured() else None,
            "configured": self.is_configured(),
            "missing_config": self.missing_config(),
            "quality_tier": self.profile.quality_tier,
            "cost_per_1k_tokens": self.profile.cost_per_1k_tokens,
            "supports_json": self.profile.supports_json,
            "tasks": list(self.profile.tasks),
        }
