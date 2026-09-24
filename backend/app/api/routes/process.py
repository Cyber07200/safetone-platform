from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.errors import LiveModeUnavailable, NotFoundError, ValidationFailed
from app.db.session import get_db
from app.models import ProcessingRun
from app.repositories import store
from app.schemas.api import ErrorResponse, HistoryPage, ProcessRequest, RunDetail
from app.services.ai.router import get_router
from app.services.demo.scenarios import BY_ID
from app.services.pipeline import execute_run, initial_stages

router = APIRouter(prefix="/api/v1", tags=["processing"])
_tasks: set[asyncio.Task] = set()

ERRORS = {404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}, 422: {"model": ErrorResponse}}


def _create_run(db: Session, req: ProcessRequest) -> ProcessingRun:
    store.get_bank(db, req.bank_id)
    product_id = req.product_id
    if product_id:
        store.get_product(db, req.bank_id, product_id)
    question, answer, origin = req.question, req.answer_text, "user"

    if req.scenario_id:
        sc = BY_ID.get(req.scenario_id)
        if not sc:
            raise NotFoundError("Сценарий не найден", details={"scenario_id": req.scenario_id})
        if req.mode != "demo":
            raise ValidationFailed("Сценарии доступны только в Demo Mode", code="SCENARIO_REQUIRES_DEMO")
        question, answer, origin = sc.question, sc.answer, "scenario"
        prod = next((p for p in store.list_products(db, req.bank_id) if p.code == sc.product_code), None)
        product_id = prod.id if prod else product_id
    elif req.mode == "demo":
        if not answer:
            raise ValidationFailed(
                "В Demo Mode генерация моделью не выполняется. Выберите сценарий или вставьте ответ AI для "
                "проверки, либо переключитесь в Live Mode.", code="DEMO_NEEDS_ANSWER")
    else:  # live
        if not answer:
            if not get_router().live_available():
                raise LiveModeUnavailable(
                    "Live Mode недоступен: не настроен ни один AI-провайдер. Добавьте ключи в backend/.env "
                    "или переключитесь в Demo Mode.")
            origin = "provider"
    run = ProcessingRun(
        bank_id=req.bank_id, product_id=product_id, mode=req.mode, question=question,
        answer_origin=origin, scenario_id=req.scenario_id, original_answer=answer, tone=req.tone,
        provider=(req.provider if origin == "provider" and req.provider not in (None, "", "auto") else None),
        stages=initial_stages(), execution_status="queued",
    )
    db.add(run)
    db.commit()
    return run


def _detail(db: Session, run: ProcessingRun) -> dict:
    db.refresh(run)
    return store.run_detail(run, store.product_names(db, run.bank_id))


@router.post("/process", response_model=RunDetail, status_code=202, responses=ERRORS,
             summary="Запустить проверку ответа AI")
async def process(req: ProcessRequest, db: Session = Depends(get_db)):
    run = _create_run(db, req)
    if req.wait:
        await execute_run(run.id)
        return JSONResponse(status_code=200, content=RunDetail(**_detail(db, run)).model_dump(mode="json"))
    task = asyncio.create_task(execute_run(run.id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return _detail(db, run)


@router.get("/process/{run_id}", response_model=RunDetail, responses=ERRORS, summary="Состояние и аудит обработки")
def get_process(run_id: str, bank_id: str = Query(...), db: Session = Depends(get_db)):
    return store.run_detail(store.get_run(db, bank_id, run_id), store.product_names(db, bank_id))


@router.post("/process/{run_id}/rerun", response_model=RunDetail, status_code=202, responses=ERRORS,
             summary="Повторить обработку с теми же входными данными")
async def rerun(run_id: str, bank_id: str = Query(...), db: Session = Depends(get_db)):
    old = store.get_run(db, bank_id, run_id)
    req = ProcessRequest(
        bank_id=bank_id, product_id=old.product_id, question=old.question, mode=old.mode,  # type: ignore[arg-type]
        scenario_id=old.scenario_id,
        answer_text=old.original_answer if old.answer_origin == "user" else None,
        provider=old.provider if old.answer_origin == "provider" else None, tone=old.tone)  # type: ignore[arg-type]
    return await process(req, db)


@router.get("/history", response_model=HistoryPage, summary="История обработок с фильтрами")
def history(bank_id: str = Query(...), status: str | None = None, mode: str | None = None,
            product_id: str | None = None, risk: str | None = None, q: str | None = Query(None, max_length=200),
            limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    rows, total = store.list_runs(db, bank_id, status=status, mode=mode, product_id=product_id, q=q, risk=risk,
                                  limit=limit, offset=offset)
    names = store.product_names(db, bank_id)
    return {"items": [store.run_summary(r, names) for r in rows], "total": total, "limit": limit, "offset": offset}
