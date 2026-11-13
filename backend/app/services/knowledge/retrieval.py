"""Lexical BM25 retrieval over document chunks, scoped per bank.

Scope rules (tenant isolation):
  * chunks of the requesting bank, and
  * global regulatory chunks (bank_scope == "global").
Chunks of other banks are never loaded.

The retriever is intentionally dependency-free; an embedding retriever
can implement the same `search()` signature later.
"""
from __future__ import annotations

import math
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Chunk, Document
from .text import content_terms

_lock = threading.Lock()
_kb_version = 0
_cache: dict[str, tuple[int, "_Index"]] = {}


def bump_kb_version() -> None:
    global _kb_version
    with _lock:
        _kb_version += 1
        _cache.clear()


def effective_actuality(doc: Document, today: date | None = None) -> str:
    """current | superseded | expired | not_yet_effective | unverified.

    Upload date is NEVER used as a proxy for legal actuality.
    """
    today = today or date.today()
    if doc.actuality_status == "superseded":
        return "superseded"
    if doc.actuality_status == "unverified":
        return "unverified"
    if doc.actuality_status == "expired":
        return "expired"
    if doc.effective_from and doc.effective_from > today:
        return "not_yet_effective"
    if doc.effective_to and doc.effective_to < today:
        return "expired"
    return "current"


@dataclass
class DocMeta:
    id: str
    title: str
    doc_type: str
    bank_id: str | None
    product_id: str | None
    version: int
    document_key: str
    document_date: str | None
    effective_from: str | None
    effective_to: str | None
    actuality: str
    actuality_note: str
    source_url: str | None
    is_demo: bool
    scope_label: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Hit:
    chunk_id: str
    text: str
    section: str
    page: int | None
    score: float
    suspicious: bool
    doc: DocMeta
    terms: list[str] = field(default_factory=list)


@dataclass
class _Entry:
    chunk_id: str
    text: str
    section: str
    page: int | None
    suspicious: bool
    tf: Counter
    length: int
    doc: DocMeta
    terms: list[str]


class _Index:
    def __init__(self, entries: list[_Entry]):
        self.entries = entries
        self.N = len(entries)
        self.avgdl = (sum(e.length for e in entries) / self.N) if self.N else 1.0
        df: Counter = Counter()
        for e in entries:
            df.update(set(e.tf))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def score(self, q_terms: list[str], e: _Entry, k1: float = 1.4, b: float = 0.75) -> float:
        s = 0.0
        for t in set(q_terms):
            f = e.tf.get(t)
            if not f:
                continue
            s += self.idf.get(t, 0.0) * f * (k1 + 1) / (f + k1 * (1 - b + b * e.length / self.avgdl))
        return s


def _meta(doc: Document, today: date) -> DocMeta:
    return DocMeta(
        id=doc.id, title=doc.title, doc_type=doc.doc_type, bank_id=doc.bank_id,
        product_id=doc.product_id, version=doc.version, document_key=doc.document_key,
        document_date=doc.document_date.isoformat() if doc.document_date else None,
        effective_from=doc.effective_from.isoformat() if doc.effective_from else None,
        effective_to=doc.effective_to.isoformat() if doc.effective_to else None,
        actuality=effective_actuality(doc, today), actuality_note=doc.actuality_note or "",
        source_url=doc.source_url, is_demo=doc.is_demo, scope_label=doc.scope_label or "",
    )


def _build(db: Session, bank_id: str) -> _Index:
    today = date.today()
    rows = db.execute(
        select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
        .where(or_(Chunk.bank_scope == bank_id, Chunk.bank_scope == "global"))
    ).all()
    metas: dict[str, DocMeta] = {}
    entries = []
    for ch, doc in rows:
        meta = metas.get(doc.id) or metas.setdefault(doc.id, _meta(doc, today))
        terms = list(ch.terms or [])
        entries.append(_Entry(ch.id, ch.text, ch.section, ch.page, ch.suspicious,
                              Counter(terms), max(len(terms), 1), meta, terms))
    return _Index(entries)


def _index_for(db: Session, bank_id: str) -> _Index:
    with _lock:
        cached = _cache.get(bank_id)
        if cached and cached[0] == _kb_version:
            return cached[1]
        version = _kb_version
    idx = _build(db, bank_id)
    with _lock:
        if version == _kb_version:
            _cache[bank_id] = (version, idx)
    return idx


def warm(db: Session, bank_id: str) -> None:
    """Build the search index ahead of the first request (reading ~3 000 chunks takes seconds)."""
    _index_for(db, bank_id)


def search(db: Session, *, bank_id: str, query: str, product_id: str | None = None,
           top_k: int = 6, min_score: float = 0.5) -> list[Hit]:
    idx = _index_for(db, bank_id)
    q = content_terms(query)
    if not q or not idx.N:
        return []
    scored = []
    for e in idx.entries:
        # product scoping: docs bound to another product are excluded
        if product_id and e.doc.product_id and e.doc.product_id != product_id:
            continue
        s = idx.score(q, e)
        if s >= min_score:
            if product_id and e.doc.product_id == product_id:
                s *= 1.15
            scored.append((s, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [Hit(e.chunk_id, e.text, e.section, e.page, round(s, 3), e.suspicious, e.doc, e.terms)
            for s, e in scored[:top_k]]
