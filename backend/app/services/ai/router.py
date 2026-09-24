"""AI Router — picks a provider per task using a transparent policy.

The policy ranks *configured* providers by: task support, bank quality
preference (economy / balanced / quality), configured cost per 1K tokens
(unknown cost is treated as neutral), observed latency and recent
availability (a simple circuit breaker). It does not claim to find the
cheapest or best model — only the best according to known configuration.
Providers are tried sequentially (never all in parallel) with bounded
retries and fallback.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.core.errors import LiveModeUnavailable, ProviderError
from .base import AIProvider, CompletionResult, Message
from .providers import build_providers

log = logging.getLogger("safetone.ai.router")

WEIGHTS = {  # (quality, cost, latency)
    "economy": (0.2, 0.6, 0.2),
    "balanced": (0.45, 0.3, 0.25),
    "quality": (0.75, 0.1, 0.15),
}
CIRCUIT_FAILURES = 3
CIRCUIT_COOLDOWN_S = 60.0


@dataclass
class ProviderHealth:
    consecutive_failures: int = 0
    open_until: float = 0.0
    latency_ema_ms: float | None = None
    last_error: str | None = None
    last_ok_at: float | None = None
    calls: int = 0
    failures: int = 0

    def available(self) -> bool:
        return time.time() >= self.open_until

    def record(self, ok: bool, latency_ms: int | None = None, error: str | None = None) -> None:
        self.calls += 1
        if ok:
            self.consecutive_failures = 0
            self.last_ok_at = time.time()
            if latency_ms is not None:
                self.latency_ema_ms = latency_ms if self.latency_ema_ms is None else 0.7 * self.latency_ema_ms + 0.3 * latency_ms
        else:
            self.failures += 1
            self.consecutive_failures += 1
            self.last_error = error
            if self.consecutive_failures >= CIRCUIT_FAILURES:
                self.open_until = time.time() + CIRCUIT_COOLDOWN_S


@dataclass
class Attempt:
    task: str
    provider: str
    model: str
    ok: bool
    attempt: int
    latency_ms: int | None = None
    error_code: str | None = None
    error: str | None = None
    tokens: int | None = None
    cost_estimate: float | None = None
    selection_reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RoutedResult:
    result: CompletionResult
    attempts: list[Attempt] = field(default_factory=list)


class AIRouter:
    def __init__(self, settings: Settings | None = None, providers: dict[str, AIProvider] | None = None):
        self.settings = settings or get_settings()
        self.providers = providers if providers is not None else build_providers(self.settings)
        self.health: dict[str, ProviderHealth] = {n: ProviderHealth() for n in self.providers}

    # ---- introspection -------------------------------------------------
    def configured(self) -> list[AIProvider]:
        return [p for p in self.providers.values() if p.is_configured()]

    def live_available(self) -> bool:
        return bool(self.configured())

    def status(self) -> list[dict]:
        out = []
        for name, p in self.providers.items():
            h = self.health[name]
            d = p.describe()
            d.update({
                "circuit_open": not h.available(),
                "latency_ema_ms": round(h.latency_ema_ms) if h.latency_ema_ms else None,
                "calls": h.calls, "failures": h.failures, "last_error": h.last_error,
                "status": ("not_configured" if not p.is_configured() else
                           "unavailable" if not h.available() else
                           "degraded" if h.consecutive_failures else
                           "ok" if h.last_ok_at else "configured"),
            })
            out.append(d)
        return out

    # ---- policy --------------------------------------------------------
    def rank(self, task: str, preference: str = "auto", quality: str = "balanced") -> list[tuple[AIProvider, str]]:
        cands = [p for p in self.configured() if task in p.profile.tasks]
        if preference not in ("auto", "", None):
            chosen = [p for p in cands if p.name == preference]
            if not chosen:
                raise LiveModeUnavailable(
                    f"Выбранный провайдер «{preference}» не настроен. Проверьте .env или выберите «auto».",
                    details={"provider": preference})
            others = [p for p in cands if p.name != preference and self.health[p.name].available()]
            return [(chosen[0], "выбран вручную в настройках")] + [(p, "резервный провайдер (fallback)") for p in others]
        cands = [p for p in cands if self.health[p.name].available()] or cands
        if not cands:
            return []
        wq, wc, wl = WEIGHTS.get(quality, WEIGHTS["balanced"])
        costs = [p.profile.cost_per_1k_tokens for p in cands if p.profile.cost_per_1k_tokens is not None]
        lats = [self.health[p.name].latency_ema_ms for p in cands if self.health[p.name].latency_ema_ms]
        max_cost, max_lat = (max(costs) if costs else None), (max(lats) if lats else None)

        def score(p: AIProvider) -> float:
            q = p.profile.quality_tier / 3
            c = 0.5 if (p.profile.cost_per_1k_tokens is None or not max_cost) else p.profile.cost_per_1k_tokens / max_cost
            lat = self.health[p.name].latency_ema_ms
            l_ = 0.5 if (lat is None or not max_lat) else lat / max_lat
            return wq * q - wc * c - wl * l_

        ranked = sorted(cands, key=score, reverse=True)
        return [(p, f"авто-выбор: политика «{quality}», балл {score(p):.2f}" + (" (основной)" if i == 0 else " (fallback)"))
                for i, p in enumerate(ranked)]

    # ---- execution -----------------------------------------------------
    async def complete(self, task: str, messages: list[Message], *, preference: str = "auto",
                       quality: str = "balanced", json_mode: bool = False, temperature: float = 0.2,
                       max_tokens: int = 800) -> RoutedResult:
        ranked = self.rank(task, preference, quality)
        if not ranked:
            raise LiveModeUnavailable("Нет настроенных AI-провайдеров. Добавьте ключи в backend/.env "
                                      "или переключитесь в Demo Mode.")
        attempts: list[Attempt] = []
        last_exc: ProviderError | None = None
        for provider, reason in ranked:
            for n in range(self.settings.ai_max_retries + 1):
                try:
                    res = await provider.complete(messages, temperature=temperature, max_tokens=max_tokens,
                                                  json_mode=json_mode and provider.profile.supports_json)
                except ProviderError as exc:
                    self.health[provider.name].record(False, error=exc.code)
                    attempts.append(Attempt(task, provider.name, provider.model, False, n + 1,
                                            error_code=exc.code, error=exc.message, selection_reason=reason))
                    log.warning("AI call failed task=%s provider=%s code=%s", task, provider.name, exc.code)
                    last_exc = exc
                    if exc.retryable and n < self.settings.ai_max_retries:
                        await asyncio.sleep(0.5 * (2 ** n))
                        continue
                    break
                self.health[provider.name].record(True, res.latency_ms)
                attempts.append(Attempt(task, res.provider, res.model, True, n + 1, res.latency_ms,
                                        tokens=res.usage.total_tokens, cost_estimate=res.cost_estimate,
                                        selection_reason=reason))
                log.info("AI call ok task=%s provider=%s model=%s latency=%sms", task, res.provider, res.model,
                         res.latency_ms)
                return RoutedResult(res, attempts)
        err = ProviderError("Все доступные AI-провайдеры вернули ошибку: " + (last_exc.message if last_exc else ""),
                            provider=last_exc.provider if last_exc else "none", code="ALL_PROVIDERS_FAILED")
        err.attempts = attempts  # type: ignore[attr-defined]
        raise err


_router: AIRouter | None = None


def get_router() -> AIRouter:
    global _router
    if _router is None:
        _router = AIRouter()
    return _router


def set_router(router: AIRouter | None) -> None:
    """Test hook / reconfiguration."""
    global _router
    _router = router
