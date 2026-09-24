"""Pydantic request/response schemas (OpenAPI contract)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings

Mode = Literal["demo", "live"]
Tone = Literal["neutral", "friendly", "concise", "detailed"]
ResultStatus = Literal["READY", "NEEDS_REVIEW", "FAILED"]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class Health(BaseModel):
    status: str
    version: str
    default_mode: Mode
    live_available: bool
    database: str


class BankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name: str
    is_demo: bool


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    bank_id: str
    code: str
    name: str
    category: str
    description: str
    is_demo: bool


class ScenarioOut(BaseModel):
    id: str
    title: str
    category: str
    product_id: str | None
    product_code: str
    question: str
    answer: str
    expected_status: str
    demonstrates: str


class ProcessRequest(BaseModel):
    bank_id: str
    product_id: str | None = None
    question: str = Field(min_length=3)
    mode: Mode = "demo"
    scenario_id: str | None = None
    answer_text: str | None = Field(default=None, description="Готовый ответ AI для проверки (без генерации)")
    provider: str | None = Field(default=None, description="auto | yandex | gigachat | openai")
    tone: Tone = "neutral"
    wait: bool = Field(default=False, description="Дождаться завершения (для интеграций и тестов)")

    @field_validator("question")
    @classmethod
    def _q_len(cls, v: str) -> str:
        v = v.strip()
        if len(v) > get_settings().max_question_chars:
            raise ValueError(f"Вопрос длиннее {get_settings().max_question_chars} символов")
        return v

    @field_validator("answer_text")
    @classmethod
    def _a_len(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > get_settings().max_answer_chars:
            raise ValueError(f"Ответ длиннее {get_settings().max_answer_chars} символов")
        return v


class StageOut(BaseModel):
    key: str
    title: str
    status: str
    method: str | None = None
    summary: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None
    warnings: list[str] = []


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    bank_id: str
    product_id: str | None
    product_name: str | None = None
    created_at: datetime
    finished_at: datetime | None
    mode: Mode
    execution_status: str
    result_status: ResultStatus | None
    max_risk: str | None
    question: str
    answer_origin: str
    scenario_id: str | None
    provider: str | None
    model: str | None
    tone: str
    duration_ms: int | None
    changes_count: int = 0


class RunDetail(RunSummary):
    original_answer: str | None
    legal_answer: str | None
    final_answer: str | None
    tokens_total: int | None
    cost_estimate: float | None
    stages: list[StageOut]
    claims: list[dict]
    sources: list[dict]
    legal_changes: list[dict]
    linguistic: dict
    semantic_check: dict
    ai_calls: list[dict]
    missing_data: list[str]
    notices: list[str]
    error: dict | None


class HistoryPage(BaseModel):
    items: list[RunSummary]
    total: int
    limit: int
    offset: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    bank_id: str | None
    product_id: str | None
    product_name: str | None = None
    document_key: str
    version: int
    title: str
    doc_type: str
    scope_label: str
    document_date: date | None
    effective_from: date | None
    effective_to: date | None
    actuality_status: str
    effective_actuality: str
    actuality_note: str
    source_url: str | None
    is_demo: bool
    is_global: bool
    original_filename: str | None
    mime_type: str | None
    size_bytes: int
    text_length: int
    chunk_count: int
    security_flags: list[str]
    uploaded_at: datetime


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ordinal: int
    section: str
    page: int | None
    text: str
    suspicious: bool


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut]


class DocumentPatch(BaseModel):
    title: str | None = None
    actuality_status: Literal["current", "superseded", "unverified", "expired"] | None = None
    actuality_note: str | None = None
    document_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    source_url: str | None = None


class BankSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    bank_id: str
    default_mode: Mode
    default_provider: str
    default_tone: Tone
    quality_preference: Literal["economy", "balanced", "quality"]
    allow_documents_to_llm: bool
    retention_days: int


class BankSettingsIn(BaseModel):
    default_mode: Mode | None = None
    default_provider: Literal["auto", "yandex", "gigachat", "openai"] | None = None
    default_tone: Tone | None = None
    quality_preference: Literal["economy", "balanced", "quality"] | None = None
    allow_documents_to_llm: bool | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)


class SettingsView(BaseModel):
    bank: BankSettingsOut
    platform: dict


class ProvidersView(BaseModel):
    live_available: bool
    default_provider: str
    routing_policy: str
    providers: list[dict]


class Stats(BaseModel):
    total_runs: int
    by_status: dict[str, int]
    by_mode: dict[str, int]
    by_risk: dict[str, int]
    claims_by_status: dict[str, int]
    corrections: int
    avg_duration_ms: int | None
    documents: int
    documents_needing_attention: int
    recent: list[RunSummary]
