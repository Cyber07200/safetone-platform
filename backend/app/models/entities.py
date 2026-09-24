"""SQLAlchemy ORM entities.

Tenant isolation: every bank-owned row carries `bank_id`. Documents with
`bank_id IS NULL` are global regulatory sources (laws, regulator
guidance) visible to every bank. Repositories always filter by bank.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer,
                        String, Text, UniqueConstraint, Index)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Bank(Base):
    __tablename__ = "banks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    products: Mapped[list[Product]] = relationship(back_populates="bank", cascade="all, delete-orphan")
    settings: Mapped[BankSettings | None] = relationship(back_populates="bank", uselist=False,
                                                          cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("bank_id", "code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bank_id: Mapped[str] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(64))  # credit_card | loan | deposit | account
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    bank: Mapped[Bank] = relationship(back_populates="products")


class BankSettings(Base):
    __tablename__ = "bank_settings"

    bank_id: Mapped[str] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), primary_key=True)
    default_mode: Mapped[str] = mapped_column(String(16), default="demo")
    default_provider: Mapped[str] = mapped_column(String(32), default="auto")
    default_tone: Mapped[str] = mapped_column(String(32), default="neutral")
    quality_preference: Mapped[str] = mapped_column(String(16), default="balanced")  # economy|balanced|quality
    allow_documents_to_llm: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    bank: Mapped[Bank] = relationship(back_populates="settings")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("bank_scope", "document_key", "version"),
        Index("ix_documents_bank_product", "bank_id", "product_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # NULL bank_id => global regulatory source shared by all banks.
    bank_id: Mapped[str | None] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), nullable=True)
    # Non-null mirror of bank_id used in the unique constraint ("global" for NULL).
    bank_scope: Mapped[str] = mapped_column(String(36), default="global")
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    document_key: Mapped[str] = mapped_column(String(120))  # logical id across versions
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(300))
    doc_type: Mapped[str] = mapped_column(String(32))  # law|regulation|contract|tariff|internal|reference
    scope_label: Mapped[str] = mapped_column(String(200), default="")

    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    # current | superseded | unverified | expired  (stored); effective status is computed
    actuality_status: Mapped[str] = mapped_column(String(16), default="unverified")
    actuality_note: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    text_length: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    security_flags: Mapped[list] = mapped_column(JSON, default=list)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list[Chunk]] = relationship(back_populates="document", cascade="all, delete-orphan",
                                               order_by="Chunk.ordinal")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    bank_scope: Mapped[str] = mapped_column(String(36), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    section: Mapped[str] = mapped_column(String(300), default="")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    terms: Mapped[list] = mapped_column(JSON, default=list)  # stemmed tokens for BM25
    suspicious: Mapped[bool] = mapped_column(Boolean, default=False)  # prompt-injection-like content

    document: Mapped[Document] = relationship(back_populates="chunks")


class ProcessingRun(Base):
    __tablename__ = "processing_runs"
    __table_args__ = (Index("ix_runs_bank_created", "bank_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    bank_id: Mapped[str] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"))
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    mode: Mapped[str] = mapped_column(String(8))  # demo | live
    execution_status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|completed|failed
    result_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # READY|NEEDS_REVIEW|FAILED
    max_risk: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tone: Mapped[str] = mapped_column(String(32), default="neutral")

    question: Mapped[str] = mapped_column(Text)
    answer_origin: Mapped[str] = mapped_column(String(16))  # scenario | provider | user
    scenario_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    original_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tokens_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stages: Mapped[list] = mapped_column(JSON, default=list)
    claims: Mapped[list] = mapped_column(JSON, default=list)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    legal_changes: Mapped[list] = mapped_column(JSON, default=list)
    linguistic: Mapped[dict] = mapped_column(JSON, default=dict)
    semantic_check: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_calls: Mapped[list] = mapped_column(JSON, default=list)
    missing_data: Mapped[list] = mapped_column(JSON, default=list)
    notices: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
