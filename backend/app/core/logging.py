"""Logging with secret masking.

Log records never contain API keys: values of configured secrets and
typical auth header patterns are redacted before emission. Question and
answer texts are not logged at INFO level (bank data stays in the DB).
"""
from __future__ import annotations

import logging
import re

from .config import get_settings

_AUTH_PATTERNS = [
    re.compile(r"(Api-Key\s+)[A-Za-z0-9_\-\.]+", re.I),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.=]+", re.I),
    re.compile(r"(Basic\s+)[A-Za-z0-9+/=]+", re.I),
    re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/@\s]+:)[^@\s]+"),  # DB password in connection URLs
]


def _secret_values() -> list[str]:
    s = get_settings()
    values = []
    for attr in ("gigachat_auth_key", "gigachat_client_secret", "chat_encryption_key"):
        v = getattr(s, attr)
        if v is not None:
            raw = v.get_secret_value()
            if raw and len(raw) >= 6:
                values.append(raw)
    return values


def redact(text: str) -> str:
    for secret in _secret_values():
        text = text.replace(secret, "[REDACTED]")
    for pat in _AUTH_PATTERNS:
        text = pat.sub(lambda m: m.group(1) + "[REDACTED]", text)
    return text


class SecretMaskingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - defensive
            return True
        red = redact(msg)
        if red != msg:
            record.msg = red
            record.args = ()
        return True


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    if not any(isinstance(f, SecretMaskingFilter) for h in root.handlers for f in h.filters):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(SecretMaskingFilter())
        root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    # httpx logs full URLs at INFO; keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
