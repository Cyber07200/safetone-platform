"""Application configuration.

All secrets are read from environment variables / backend `.env` only.
Nothing in this module is ever serialized to the frontend except via
`public_view()`, which masks secrets.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- general ---------------------------------------------------------
    safetone_mode: Literal["demo", "live"] = "demo"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'safetone.db').as_posix()}"
    storage_dir: Path = BACKEND_DIR / "storage"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"
    auto_seed_demo: bool = True
    seed_laws: bool = True  # load app/seed/laws/*.md into the knowledge base on startup

    # --- limits ----------------------------------------------------------
    max_question_chars: int = 2_000
    max_answer_chars: int = 8_000
    max_upload_bytes: int = 10 * 1024 * 1024
    max_document_chars: int = 2_000_000
    retrieval_top_k: int = 6

    # --- AI providers ----------------------------------------------------
    default_ai_provider: str = "auto"  # auto | gigachat
    ai_request_timeout_s: float = 30.0
    ai_max_retries: int = 1  # retries per provider on retryable errors
    # Whether bank documents may be sent to external LLM providers as context.
    allow_documents_to_llm: bool = False

    gigachat_auth_key: SecretStr | None = None  # base64(client_id:client_secret)
    gigachat_client_id: str | None = None
    gigachat_client_secret: SecretStr | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://api.giga.chat/v1"
    gigachat_ca_bundle: str | None = None  # path to Russian Trusted Root CA bundle
    gigachat_cost_per_1k_tokens: float | None = None

    # --- chat history encryption ---------------------------------------
    # 32-byte key, base64. Generate: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
    chat_encryption_key: SecretStr | None = None
    chat_history_window: int = 20  # recent messages sent to the model verbatim
    max_chat_message_chars: int = 4_000

    @field_validator(
        "gigachat_auth_key", "gigachat_client_secret", "chat_encryption_key", mode="before",
    )
    @classmethod
    def _empty_secret_is_none(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator(
        "gigachat_client_id", "gigachat_ca_bundle", mode="before",
    )
    @classmethod
    def _empty_str_is_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("gigachat_cost_per_1k_tokens", mode="before")
    @classmethod
    def _empty_float_is_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_dir(self) -> Path:
        return Path(self.storage_dir) / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "••••"
    return f"{value[:3]}••••{value[-2:]}"


# Field-name based detection of secrets, used by the log filter.
SECRET_ENV_NAMES = ("GIGACHAT_AUTH_KEY", "GIGACHAT_CLIENT_SECRET", "CHAT_ENCRYPTION_KEY", "DATABASE_URL")
