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

    # --- limits ----------------------------------------------------------
    max_question_chars: int = 2_000
    max_answer_chars: int = 8_000
    max_upload_bytes: int = 10 * 1024 * 1024
    max_document_chars: int = 2_000_000
    retrieval_top_k: int = 6

    # --- AI providers ----------------------------------------------------
    default_ai_provider: str = "auto"  # auto | yandex | gigachat | openai
    ai_request_timeout_s: float = 30.0
    ai_max_retries: int = 1  # retries per provider on retryable errors
    # Whether bank documents may be sent to external LLM providers as context.
    allow_documents_to_llm: bool = False

    yandex_api_key: SecretStr | None = None
    yandex_iam_token: SecretStr | None = None
    yandex_folder_id: str | None = None
    yandex_model_uri: str | None = None  # e.g. gpt://<folder>/yandexgpt-lite/latest
    yandex_base_url: str = "https://llm.api.cloud.yandex.net/foundationModels/v1"
    yandex_cost_per_1k_tokens: float | None = None

    gigachat_auth_key: SecretStr | None = None  # base64(client_id:client_secret)
    gigachat_client_id: str | None = None
    gigachat_client_secret: SecretStr | None = None
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat"
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://api.giga.chat/v1"
    gigachat_ca_bundle: str | None = None  # path to Russian Trusted Root CA bundle
    gigachat_cost_per_1k_tokens: float | None = None

    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None
    openai_provider_label: str = "OpenAI-compatible"
    openai_cost_per_1k_tokens: float | None = None

    @field_validator(
        "yandex_api_key", "yandex_iam_token", "gigachat_auth_key",
        "gigachat_client_secret", "openai_api_key", mode="before",
    )
    @classmethod
    def _empty_secret_is_none(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator(
        "yandex_folder_id", "yandex_model_uri", "gigachat_client_id",
        "openai_base_url", "openai_model", "gigachat_ca_bundle", mode="before",
    )
    @classmethod
    def _empty_str_is_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator(
        "yandex_cost_per_1k_tokens", "gigachat_cost_per_1k_tokens",
        "openai_cost_per_1k_tokens", mode="before",
    )
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
SECRET_ENV_NAMES = (
    "YANDEX_API_KEY", "YANDEX_IAM_TOKEN", "GIGACHAT_AUTH_KEY",
    "GIGACHAT_CLIENT_SECRET", "OPENAI_API_KEY",
)
