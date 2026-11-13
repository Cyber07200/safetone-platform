"""Data access with mandatory bank scoping (tenant isolation)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Bank, BankSettings, Document, ProcessingRun, Product
from app.services.knowledge.retrieval import effective_actuality


# ---- banks / products ---------------------------------------------------
def list_banks(db: Session) -> list[Bank]:
    return list(db.scalars(select(Bank).order_by(Bank.created_at)))


def get_bank(db: Session, bank_id: str) -> Bank:
    bank = db.get(Bank, bank_id)
    if not bank:
        raise NotFoundError("Банк не найден", details={"bank_id": bank_id})
    return bank


def list_products(db: Session, bank_id: str) -> list[Product]:
    get_bank(db, bank_id)
    return list(db.scalars(select(Product).where(Product.bank_id == bank_id).order_by(Product.name)))


def get_product(db: Session, bank_id: str, product_id: str) -> Product:
    p = db.get(Product, product_id)
    if not p or p.bank_id != bank_id:
        raise NotFoundError("Продукт не найден в этом банке", details={"product_id": product_id})
    return p


def get_settings_row(db: Session, bank_id: str) -> BankSettings:
    get_bank(db, bank_id)
    s = db.get(BankSettings, bank_id)
    if not s:
        s = BankSettings(bank_id=bank_id)
        db.add(s)
        db.commit()
    return s


# ---- documents --------------------------------------------------------------
def document_view(doc: Document, product_names: dict[str, str]) -> dict:
    return {
        **{c.name: getattr(doc, c.name) for c in Document.__table__.columns},
        "product_name": product_names.get(doc.product_id or ""),
        "effective_actuality": effective_actuality(doc),
        "is_global": doc.bank_id is None,
        "security_flags": doc.security_flags or [],
    }


def list_documents(db: Session, bank_id: str, *, include_global: bool = True, doc_type: str | None = None,
                   q: str | None = None) -> list[Document]:
    get_bank(db, bank_id)
    cond = or_(Document.bank_id == bank_id, Document.bank_id.is_(None)) if include_global else Document.bank_id == bank_id
    stmt = select(Document).where(cond)
    if doc_type:
        stmt = stmt.where(Document.doc_type == doc_type)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%"))
    return list(db.scalars(stmt.order_by(Document.document_key, Document.version.desc())))


def get_document(db: Session, bank_id: str, doc_id: str) -> Document:
    doc = db.get(Document, doc_id)
    # another bank's document is reported as "not found" — its existence is not disclosed
    if not doc or (doc.bank_id is not None and doc.bank_id != bank_id):
        raise NotFoundError("Документ не найден")
    return doc


def product_names(db: Session, bank_id: str) -> dict[str, str]:
    return {p.id: p.name for p in db.scalars(select(Product).where(Product.bank_id == bank_id))}


# ---- runs ---------------------------------------------------------------------
def get_run(db: Session, bank_id: str, run_id: str) -> ProcessingRun:
    run = db.get(ProcessingRun, run_id)
    if not run or run.bank_id != bank_id:
        raise NotFoundError("Обработка не найдена")
    return run


def list_runs(db: Session, bank_id: str, *, status: str | None = None, mode: str | None = None,
              product_id: str | None = None, q: str | None = None, risk: str | None = None,
              limit: int = 20, offset: int = 0) -> tuple[list[ProcessingRun], int]:
    get_bank(db, bank_id)
    stmt = select(ProcessingRun).where(ProcessingRun.bank_id == bank_id)
    if status:
        stmt = stmt.where(ProcessingRun.result_status == status)
    if mode:
        stmt = stmt.where(ProcessingRun.mode == mode)
    if product_id:
        stmt = stmt.where(ProcessingRun.product_id == product_id)
    if risk:
        stmt = stmt.where(ProcessingRun.max_risk == risk)
    if q:
        stmt = stmt.where(ProcessingRun.question.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(db.scalars(stmt.order_by(ProcessingRun.created_at.desc()).limit(limit).offset(offset)))
    return rows, total


def run_summary(run: ProcessingRun, names: dict[str, str]) -> dict:
    return {
        "id": run.id, "bank_id": run.bank_id, "product_id": run.product_id,
        "product_name": names.get(run.product_id or ""), "created_at": run.created_at,
        "finished_at": run.finished_at, "mode": run.mode, "execution_status": run.execution_status,
        "result_status": run.result_status, "max_risk": run.max_risk, "question": run.question,
        "answer_origin": run.answer_origin, "scenario_id": run.scenario_id, "provider": run.provider,
        "model": run.model, "tone": run.tone, "duration_ms": run.duration_ms,
        "changes_count": len(run.legal_changes or []),
    }


def run_detail(run: ProcessingRun, names: dict[str, str]) -> dict:
    d = run_summary(run, names)
    d.update({k: getattr(run, k) for k in (
        "original_answer", "legal_answer", "final_answer", "tokens_total", "cost_estimate", "stages", "claims",
        "sources", "legal_changes", "linguistic", "semantic_check", "ai_calls", "missing_data", "notices", "error")})
    for k in ("claims", "sources", "legal_changes", "ai_calls", "missing_data", "notices", "stages"):
        d[k] = d[k] or []
    for k in ("linguistic", "semantic_check"):
        d[k] = d[k] or {}
    return d


def purge_expired_runs(db: Session) -> int:
    """Retention policy: delete runs older than each bank's retention_days."""
    removed = 0
    for s in db.scalars(select(BankSettings)):
        cutoff = datetime.now(timezone.utc) - timedelta(days=s.retention_days)
        res = db.execute(delete(ProcessingRun).where(ProcessingRun.bank_id == s.bank_id,
                                                     ProcessingRun.created_at < cutoff))
        removed += res.rowcount or 0
    db.commit()
    return removed


def fail_interrupted_runs(db: Session) -> int:
    """Runs left queued/running by a server stop can never finish: mark them FAILED so clients stop polling."""
    runs = list(db.scalars(select(ProcessingRun).where(ProcessingRun.execution_status.in_(("queued", "running")))))
    now = datetime.now(timezone.utc)
    for run in runs:
        run.stages = [dict(s, status="skipped", summary="Не выполнялся: обработка прервана перезапуском сервера")
                      if s.get("status") in ("pending", "running") else s for s in (run.stages or [])]
        run.error = {"code": "INTERRUPTED", "message": "Обработка прервана перезапуском сервера. Запустите её повторно.",
                     "stage": None}
        run.execution_status = "failed"
        run.result_status = "FAILED"
        run.final_answer = None
        run.finished_at = now
    db.commit()
    return len(runs)
