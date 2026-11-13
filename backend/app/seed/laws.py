"""Load texts of banking laws (app/seed/laws/*.md, see scripts/fetch_laws.py)
into the knowledge base as global sources shared by all banks.

Idempotent: a law whose text is already stored is skipped; a changed text
becomes a new version and the previous one is marked superseded.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document
from app.services.knowledge.ingest import DocumentMeta, ingest_text

log = logging.getLogger("safetone.seed.laws")
LAWS = Path(__file__).parent / "laws"


def _meta(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text("utf-8").splitlines() if "=" in line)


def seed_laws(db: Session) -> int:
    added = 0
    for md in sorted(LAWS.glob("*.md")):
        meta = _meta(md.with_suffix(".meta"))
        text = md.read_text("utf-8")
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if db.scalar(select(Document.id).where(Document.bank_scope == "global", Document.sha256 == sha)):
            continue
        fetched = date.fromisoformat(meta["fetched"])
        ingest_text(db, bank_id=None, text=text, meta=DocumentMeta(
            title=meta["title"], doc_type="law", document_key=md.stem, scope_label="Российская Федерация · все банки",
            document_date=date.fromisoformat(meta["adopted"]), actuality_status="current",
            actuality_note=(f"Действующая редакция по данным справочной системы ГАРАНТ на {fetched:%d.%m.%Y}. "
                            "Официальный источник — pravo.gov.ru. Перед юридически значимым использованием "
                            "сверьте редакцию."),
            source_url=meta["source_url"]))
        added += 1
        log.info("Law loaded: %s", md.stem)
    if added:
        db.commit()
    return added
