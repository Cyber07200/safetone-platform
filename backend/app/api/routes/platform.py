"""Health, catalog (banks/products/scenarios), providers, settings, stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.db.session import get_db
from app.models import ProcessingRun
from app.repositories import store
from app.schemas.api import (BankOut, BankSettingsIn, BankSettingsOut, ErrorResponse, Health, ProductOut,
                             ProvidersView, ScenarioOut, SettingsView, Stats)
from app.services.ai.base import Message
from app.services.ai.router import WEIGHTS, get_router
from app.services.demo.scenarios import SCENARIOS
from app.services.knowledge.retrieval import effective_actuality
from app.services.linguistic.rewriter import TONES

router = APIRouter(tags=["platform"])


@router.get("/api/health", response_model=Health, summary="Состояние сервиса")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_state = "ok"
    except Exception:  # pragma: no cover
        db_state = "error"
    s = get_settings()
    return {"status": "ok" if db_state == "ok" else "degraded", "version": __version__, "default_mode": s.safetone_mode,
            "live_available": get_router().live_available(), "database": db_state}


@router.get("/api/v1/banks", response_model=list[BankOut], tags=["catalog"])
def banks(db: Session = Depends(get_db)):
    return store.list_banks(db)


@router.get("/api/v1/products", response_model=list[ProductOut], tags=["catalog"])
def products(bank_id: str = Query(...), db: Session = Depends(get_db)):
    return store.list_products(db, bank_id)


@router.get("/api/v1/scenarios", response_model=list[ScenarioOut], tags=["catalog"],
            summary="Демонстрационные сценарии (заранее подготовленные ответы)")
def scenarios(bank_id: str = Query(...), db: Session = Depends(get_db)):
    by_code = {p.code: p.id for p in store.list_products(db, bank_id)}
    return [{**s.to_dict(), "product_id": by_code.get(s.product_code)} for s in SCENARIOS]


@router.get("/api/v1/providers", response_model=ProvidersView, tags=["ai"])
def providers():
    r = get_router()
    return {"live_available": r.live_available(), "default_provider": get_settings().default_ai_provider,
            "routing_policy": "Выбор среди настроенных провайдеров по поддержке задачи, предпочтению качества банка "
                              "(economy/balanced/quality), стоимости из конфигурации и наблюдаемой задержке; "
                              "последовательный fallback, ограниченные повторы, circuit breaker. Веса: "
                              + "; ".join(f"{k}: качество {w[0]}, стоимость {w[1]}, задержка {w[2]}"
                                          for k, w in WEIGHTS.items()),
            "providers": r.status()}


@router.post("/api/v1/providers/{name}/check", tags=["ai"], responses={404: {"model": ErrorResponse}},
             summary="Проверить доступность провайдера (выполняет реальный короткий запрос)")
async def check_provider(name: str):
    r = get_router()
    p = r.providers.get(name)
    if not p:
        raise NotFoundError("Провайдер не найден")
    if not p.is_configured():
        return {"provider": name, "ok": False, "code": "PROVIDER_NOT_CONFIGURED",
                "message": "Не настроено: " + ", ".join(p.missing_config())}
    from app.core.errors import ProviderError
    try:
        res = await p.complete([Message("user", "Ответь одним словом: ок")], max_tokens=5, temperature=0)
        r.health[name].record(True, res.latency_ms)
        return {"provider": name, "ok": True, "model": res.model, "latency_ms": res.latency_ms}
    except ProviderError as exc:
        r.health[name].record(False, error=exc.code)
        return {"provider": name, "ok": False, "code": exc.code, "message": exc.message}


def _settings_view(db: Session, bank_id: str) -> dict:
    row = store.get_settings_row(db, bank_id)
    s = get_settings()
    return {"bank": BankSettingsOut.model_validate(row).model_dump(), "platform": {
        "default_mode": s.safetone_mode, "max_question_chars": s.max_question_chars,
        "max_answer_chars": s.max_answer_chars, "max_upload_mb": s.max_upload_bytes // (1024 * 1024),
        "allowed_formats": ["PDF", "DOCX", "HTML", "TXT", "MD"], "tones": TONES,
        "ai_request_timeout_s": s.ai_request_timeout_s, "ai_max_retries": s.ai_max_retries,
        "database": "sqlite" if s.database_url.startswith("sqlite") else "postgresql",
    }}


@router.get("/api/v1/settings", response_model=SettingsView, tags=["settings"])
def get_bank_settings(bank_id: str = Query(...), db: Session = Depends(get_db)):
    return _settings_view(db, bank_id)


@router.put("/api/v1/settings", response_model=SettingsView, tags=["settings"])
def put_bank_settings(body: BankSettingsIn, bank_id: str = Query(...), db: Session = Depends(get_db)):
    row = store.get_settings_row(db, bank_id)
    for k, v in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(row, k, v)
    db.commit()
    return _settings_view(db, bank_id)


@router.get("/api/v1/stats", response_model=Stats, tags=["analytics"])
def stats(bank_id: str = Query(...), db: Session = Depends(get_db)):
    store.get_bank(db, bank_id)
    runs = list(db.scalars(select(ProcessingRun).where(ProcessingRun.bank_id == bank_id)))
    by_status: dict[str, int] = {}
    by_mode: dict[str, int] = {}
    by_risk: dict[str, int] = {}
    claims: dict[str, int] = {}
    corrections = 0
    durations = []
    for r in runs:
        by_status[r.result_status or r.execution_status] = by_status.get(r.result_status or r.execution_status, 0) + 1
        by_mode[r.mode] = by_mode.get(r.mode, 0) + 1
        if r.max_risk:
            by_risk[r.max_risk] = by_risk.get(r.max_risk, 0) + 1
        for c in r.claims or []:
            if c.get("substantive"):
                claims[c["status"]] = claims.get(c["status"], 0) + 1
        corrections += len(r.legal_changes or [])
        if r.duration_ms is not None:
            durations.append(r.duration_ms)
    docs = store.list_documents(db, bank_id)
    attention = sum(1 for d in docs if effective_actuality(d) != "current")
    names = store.product_names(db, bank_id)
    recent = sorted(runs, key=lambda r: r.created_at, reverse=True)[:6]
    return {"total_runs": len(runs), "by_status": by_status, "by_mode": by_mode, "by_risk": by_risk,
            "claims_by_status": claims, "corrections": corrections,
            "avg_duration_ms": int(sum(durations) / len(durations)) if durations else None,
            "documents": len(docs), "documents_needing_attention": attention,
            "recent": [store.run_summary(r, names) for r in recent]}

