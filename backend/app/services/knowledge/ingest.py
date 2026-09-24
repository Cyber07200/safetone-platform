"""Document ingestion: validation, storage, extraction, chunking, versioning."""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.models import Chunk, Document
from .chunking import chunk_pages
from .extract import ALLOWED, ExtractedPage, detect_kind, extract_text
from .retrieval import bump_kb_version
from .text import content_terms, normalize

DOC_TYPES = ("law", "regulation", "contract", "tariff", "internal", "reference")
ACTUALITY = ("current", "superseded", "unverified", "expired")


@dataclass
class DocumentMeta:
    title: str
    doc_type: str
    document_key: str | None = None
    product_id: str | None = None
    scope_label: str = ""
    document_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    actuality_status: str = "unverified"
    actuality_note: str = ""
    source_url: str | None = None
    is_demo: bool = False
    supersede_previous: bool = True


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9а-я]+", "-", text.lower()).strip("-")
    return s[:100] or "document"


def safe_filename(name: str) -> str:
    """Strip any path component and dangerous characters (path traversal guard)."""
    base = re.split(r"[\\/]", name)[-1]
    base = re.sub(r"[^\w.\- ()А-Яа-яЁё]", "_", base).strip(" .")
    return base[:200] or "file"


def _validate_meta(meta: DocumentMeta) -> None:
    if meta.doc_type not in DOC_TYPES:
        raise ValidationFailed(f"Неизвестный тип документа: {meta.doc_type}")
    if meta.actuality_status not in ACTUALITY:
        raise ValidationFailed(f"Неизвестный статус актуальности: {meta.actuality_status}")
    if not meta.title.strip():
        raise ValidationFailed("Название документа обязательно")
    if meta.effective_from and meta.effective_to and meta.effective_to < meta.effective_from:
        raise ValidationFailed("Дата окончания действия раньше даты начала")
    if meta.source_url and not re.match(r"^https?://", meta.source_url):
        raise ValidationFailed("Ссылка на источник должна начинаться с http:// или https://")


def _store(db: Session, *, bank_id: str | None, meta: DocumentMeta, pages: list[ExtractedPage],
           original_filename: str | None, stored_filename: str | None, mime: str | None,
           size: int, sha: str) -> Document:
    settings = get_settings()
    scope = bank_id or "global"
    pages = [ExtractedPage(normalize(p.text), p.page) for p in pages]
    total_chars = sum(len(p.text) for p in pages)
    if total_chars == 0:
        raise ValidationFailed("В документе не найден текст", code="EMPTY_DOCUMENT")
    if total_chars > settings.max_document_chars:
        raise ValidationFailed("Документ слишком большой для обработки", code="DOCUMENT_TOO_LARGE")

    dup = db.scalar(select(Document).where(Document.bank_scope == scope, Document.sha256 == sha))
    if dup:
        raise ValidationFailed(f"Этот файл уже загружен: «{dup.title}» (версия {dup.version})",
                               code="DUPLICATE_DOCUMENT", details={"document_id": dup.id})

    key = meta.document_key or _slug(meta.title)
    prev_max = db.scalar(select(func.max(Document.version)).where(
        Document.bank_scope == scope, Document.document_key == key)) or 0
    if prev_max and meta.supersede_previous and meta.actuality_status == "current":
        for old in db.scalars(select(Document).where(
                Document.bank_scope == scope, Document.document_key == key,
                Document.actuality_status == "current")):
            old.actuality_status = "superseded"
            if not old.effective_to and meta.effective_from:
                old.effective_to = meta.effective_from

    drafts = chunk_pages(pages)
    doc = Document(
        bank_id=bank_id, bank_scope=scope, product_id=meta.product_id, document_key=key,
        version=prev_max + 1, title=meta.title.strip()[:300], doc_type=meta.doc_type,
        scope_label=meta.scope_label, document_date=meta.document_date,
        effective_from=meta.effective_from, effective_to=meta.effective_to,
        actuality_status=meta.actuality_status, actuality_note=meta.actuality_note,
        source_url=meta.source_url, is_demo=meta.is_demo, original_filename=original_filename,
        stored_filename=stored_filename, mime_type=mime, size_bytes=size, sha256=sha,
        text_length=total_chars, chunk_count=len(drafts),
        security_flags=(["prompt_injection_suspected"] if any(d.suspicious for d in drafts) else []),
    )
    db.add(doc)
    db.flush()
    for d in drafts:
        db.add(Chunk(document_id=doc.id, bank_scope=scope, ordinal=d.ordinal, section=d.section[:300],
                     page=d.page, text=d.text, terms=content_terms(d.section + " " + d.text),
                     suspicious=d.suspicious))
    db.flush()
    bump_kb_version()
    return doc


def ingest_text(db: Session, *, bank_id: str | None, meta: DocumentMeta, text: str) -> Document:
    _validate_meta(meta)
    data = text.encode("utf-8")
    return _store(db, bank_id=bank_id, meta=meta, pages=[ExtractedPage(text)], original_filename=None,
                  stored_filename=None, mime="text/markdown", size=len(data),
                  sha=hashlib.sha256(data).hexdigest())


def ingest_upload(db: Session, *, bank_id: str | None, meta: DocumentMeta, filename: str,
                  data: bytes) -> Document:
    settings = get_settings()
    _validate_meta(meta)
    if not data:
        raise ValidationFailed("Файл пуст", code="EMPTY_DOCUMENT")
    if len(data) > settings.max_upload_bytes:
        raise ValidationFailed(
            f"Файл больше {settings.max_upload_bytes // (1024 * 1024)} МБ", code="FILE_TOO_LARGE")
    clean_name = safe_filename(filename)
    kind = detect_kind(clean_name, data)
    pages = extract_text(kind, data)
    sha = hashlib.sha256(data).hexdigest()

    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{kind}"
    target = (upload_dir / stored).resolve()
    if upload_dir.resolve() not in target.parents:  # defence in depth
        raise ValidationFailed("Недопустимый путь файла", code="INVALID_PATH")
    doc = _store(db, bank_id=bank_id, meta=meta, pages=pages, original_filename=clean_name,
                 stored_filename=stored, mime=ALLOWED.get(kind), size=len(data), sha=sha)
    target.write_bytes(data)
    return doc
