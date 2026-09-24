from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError, ValidationFailed
from app.db.session import get_db
from app.repositories import store
from app.schemas.api import DocumentDetail, DocumentOut, DocumentPatch, ErrorResponse
from app.services.knowledge.ingest import DocumentMeta, ingest_upload
from app.services.knowledge.retrieval import bump_kb_version

router = APIRouter(prefix="/api/v1/documents", tags=["knowledge base"])
ERRORS = {404: {"model": ErrorResponse}, 413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


def _parse_date(v: str | None, field: str) -> date | None:
    if not v:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError as exc:
        raise ValidationFailed(f"Некорректная дата в поле {field} (ожидается ГГГГ-ММ-ДД)") from exc


@router.get("", response_model=list[DocumentOut], summary="Документы банка и общие нормативные источники")
def list_documents(bank_id: str = Query(...), include_global: bool = True, doc_type: str | None = None,
                   q: str | None = Query(None, max_length=200), db: Session = Depends(get_db)):
    names = store.product_names(db, bank_id)
    return [store.document_view(d, names) for d in store.list_documents(
        db, bank_id, include_global=include_global, doc_type=doc_type, q=q)]


@router.post("", response_model=DocumentOut, status_code=201, responses=ERRORS, summary="Загрузить документ")
async def upload_document(
    bank_id: str = Form(...),
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=300),
    doc_type: str = Form(...),
    product_id: str | None = Form(None),
    document_key: str | None = Form(None),
    document_date: str | None = Form(None),
    effective_from: str | None = Form(None),
    effective_to: str | None = Form(None),
    actuality_status: str = Form("unverified"),
    actuality_note: str = Form(""),
    source_url: str | None = Form(None),
    db: Session = Depends(get_db),
):
    bank = store.get_bank(db, bank_id)
    if product_id:
        store.get_product(db, bank_id, product_id)
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise AppError(f"Файл больше {limit // (1024 * 1024)} МБ", code="FILE_TOO_LARGE", status_code=413)
    meta = DocumentMeta(
        title=title, doc_type=doc_type, product_id=product_id or None, document_key=document_key or None,
        document_date=_parse_date(document_date, "document_date"),
        effective_from=_parse_date(effective_from, "effective_from"),
        effective_to=_parse_date(effective_to, "effective_to"), actuality_status=actuality_status,
        actuality_note=actuality_note, source_url=source_url or None, scope_label=bank.name,
    )
    doc = ingest_upload(db, bank_id=bank_id, meta=meta, filename=file.filename or "file", data=data)
    db.commit()
    return store.document_view(doc, store.product_names(db, bank_id))


@router.get("/{doc_id}", response_model=DocumentDetail, responses=ERRORS, summary="Документ с фрагментами")
def get_document(doc_id: str, bank_id: str = Query(...), db: Session = Depends(get_db)):
    doc = store.get_document(db, bank_id, doc_id)
    view = store.document_view(doc, store.product_names(db, bank_id))
    view["chunks"] = doc.chunks
    return view


@router.patch("/{doc_id}", response_model=DocumentOut, responses=ERRORS, summary="Обновить метаданные документа")
def patch_document(doc_id: str, patch: DocumentPatch, bank_id: str = Query(...), db: Session = Depends(get_db)):
    doc = store.get_document(db, bank_id, doc_id)
    if doc.bank_id is None:
        raise AppError("Общие нормативные источники редактируются администратором платформы",
                       code="FORBIDDEN", status_code=403)
    for k, v in patch.model_dump(exclude_unset=True).items():
        setattr(doc, k, v)
    if doc.effective_from and doc.effective_to and doc.effective_to < doc.effective_from:
        raise ValidationFailed("Дата окончания действия раньше даты начала")
    db.commit()
    bump_kb_version()
    return store.document_view(doc, store.product_names(db, bank_id))


@router.delete("/{doc_id}", status_code=204, responses=ERRORS, summary="Удалить документ банка")
def delete_document(doc_id: str, bank_id: str = Query(...), db: Session = Depends(get_db)):
    doc = store.get_document(db, bank_id, doc_id)
    if doc.bank_id is None:
        raise AppError("Общие нормативные источники нельзя удалить из банка", code="FORBIDDEN", status_code=403)
    stored = doc.stored_filename
    db.delete(doc)
    db.commit()
    bump_kb_version()
    if stored:
        path = (get_settings().upload_dir / stored).resolve()
        if get_settings().upload_dir.resolve() in path.parents and path.exists():
            path.unlink()
