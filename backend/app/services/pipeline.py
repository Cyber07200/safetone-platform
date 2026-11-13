"""SafeTone processing pipeline.

USER QUESTION → AI GENERATION → CLAIM EXTRACTION → SOURCE RETRIEVAL →
LEGAL VERIFICATION → LEGAL CORRECTION → LINGUISTIC REWRITE →
SEMANTIC VALIDATION → FINAL RESPONSE

Every stage writes its real state to the database as it runs, so the
UI polls actual progress. A failed stage marks the run FAILED; later
stages are recorded as skipped — never as successful.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import AppError, ProviderError
from app.db.session import SessionLocal
from app.models import BankSettings, ProcessingRun, Product
from app.services.ai.prompts import generation_messages, parse_json_object, rewrite_messages, verification_messages
from app.services.ai.router import AIRouter, get_router
from app.services.knowledge import retrieval
from app.services.knowledge.text import content_terms
from app.services.legal.engine import analyze, finalize, merge_llm
from app.services.legal.policy import max_risk
from app.services.linguistic.rewriter import TONES, rewrite
from app.services.linguistic.semantic import validate

log = logging.getLogger("safetone.pipeline")

STAGES = [
    ("generation", "Генерация ответа AI"),
    ("claim_extraction", "Извлечение утверждений"),
    ("source_retrieval", "Поиск источников"),
    ("legal_verification", "Юридическая проверка"),
    ("legal_correction", "Юридическая корректировка"),
    ("linguistic_rewrite", "Лингвистическая обработка"),
    ("semantic_validation", "Проверка сохранения смысла"),
    ("final_response", "Финальный ответ"),
]


def initial_stages() -> list[dict]:
    return [{"key": k, "title": t, "status": "pending", "method": None, "summary": None,
             "started_at": None, "finished_at": None, "duration_ms": None, "warnings": []} for k, t in STAGES]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _StageTracker:
    def __init__(self, db: Session, run: ProcessingRun):
        self.db, self.run = db, run
        self._t0: dict[str, float] = {}

    def _set(self, key: str, *, persist: bool = True, **kw) -> None:
        stages = [dict(s) for s in self.run.stages]
        for s in stages:
            if s["key"] == key:
                s.update(kw)
        self.run.stages = stages
        if persist:
            self.db.commit()

    def start(self, key: str, method: str | None = None, *, slow: bool = False) -> None:
        # Each commit is a network round trip to the database (~0.5 s to a remote Postgres): a "running"
        # state is written only before slow work (a GigaChat call); local stages take milliseconds.
        self._t0[key] = time.perf_counter()
        self._set(key, persist=slow, status="running", method=method, started_at=_now().isoformat())

    def done(self, key: str, summary: str, *, method: str | None = None, warnings: list[str] | None = None,
             status: str = "completed") -> None:
        kw = dict(status=status, summary=summary, finished_at=_now().isoformat(),
                  duration_ms=int((time.perf_counter() - self._t0.get(key, time.perf_counter())) * 1000),
                  warnings=warnings or [])
        if method:
            kw["method"] = method
        self._set(key, **kw)

    def fail_rest(self, failed_key: str, message: str) -> None:
        stages = [dict(s) for s in self.run.stages]
        hit = False
        for s in stages:
            if s["key"] == failed_key:
                hit = True
                s.update(status="failed", summary=message, finished_at=_now().isoformat())
            elif hit or s["status"] in ("pending", "running"):
                if s["status"] in ("pending", "running"):
                    s.update(status="skipped", summary="Не выполнялся: предыдущий этап завершился ошибкой")
        self.run.stages = stages
        self.db.commit()


def _sources_for_llm(analyzed, limit: int = 12) -> tuple[list[dict], dict[str, retrieval.Hit]]:
    seen: dict[str, retrieval.Hit] = {}
    for a in analyzed:
        for h in a.hits:
            if h.suspicious or h.chunk_id in seen:
                continue
            seen[h.chunk_id] = h
    hits = list(seen.values())[:limit]
    out, by_sid = [], {}
    for i, h in enumerate(hits, 1):
        sid = f"s{i}"
        by_sid[sid] = h
        out.append({"sid": sid, "title": h.doc.title, "section": h.section, "actuality": h.doc.actuality,
                    "text": h.text})
    return out, by_sid


def _validate_llm_judgements(data: dict | None, by_sid: dict[str, retrieval.Hit]) -> dict[str, dict]:
    result: dict[str, dict] = {}
    if not data or not isinstance(data.get("claims"), list):
        return result
    allowed = {"CONFIRMED", "CONTRADICTED", "UNVERIFIED", "NEEDS_REVIEW"}
    for item in data["claims"]:
        if not isinstance(item, dict) or item.get("status") not in allowed or not isinstance(item.get("id"), str):
            continue
        j = {"status": item["status"], "explanation": str(item.get("explanation", ""))[:500],
             "quote": str(item.get("quote", ""))[:500], "valid": True, "current": False}
        if j["status"] in ("CONFIRMED", "CONTRADICTED"):
            sids = [s for s in item.get("source_ids", []) if s in by_sid] if isinstance(item.get("source_ids"), list) else []
            q_terms = set(content_terms(j["quote"]))
            ok = False
            for sid in sids:
                h = by_sid[sid]
                if q_terms and len(q_terms & set(h.terms)) / len(q_terms) >= 0.8:
                    ok, j["current"] = True, h.doc.actuality == "current"
                    break
            j["valid"] = ok
        result[item["id"]] = j
    return result


async def execute_run(run_id: str, *, router: AIRouter | None = None) -> None:
    """Run the pipeline for a stored ProcessingRun. Safe to call in background."""
    db = SessionLocal()
    try:
        run = db.get(ProcessingRun, run_id)
        if run is None:
            return
        await _execute(db, run, router or get_router())
    finally:
        db.close()


async def _execute(db: Session, run: ProcessingRun, router: AIRouter) -> None:
    t_start = time.perf_counter()
    tr = _StageTracker(db, run)
    run.execution_status = "running"
    db.commit()
    bank_settings = db.get(BankSettings, run.bank_id)
    quality = bank_settings.quality_preference if bank_settings else "balanced"
    docs_to_llm = bool(bank_settings and bank_settings.allow_documents_to_llm)
    preference = (run.provider or (bank_settings.default_provider if bank_settings else "auto")) or "auto"
    product = db.get(Product, run.product_id) if run.product_id else None
    ai_calls: list[dict] = []
    tokens_total = 0
    cost_total: float | None = None
    current = "generation"

    def account(routed) -> None:
        nonlocal tokens_total, cost_total
        ai_calls.extend(a.to_dict() for a in routed.attempts)
        if routed.result.usage.total_tokens:
            tokens_total += routed.result.usage.total_tokens
        if routed.result.cost_estimate is not None:
            cost_total = (cost_total or 0) + routed.result.cost_estimate

    try:
        # 1. GENERATION ---------------------------------------------------
        if run.answer_origin == "scenario":
            tr.start(current, "demo_scenario")
            tr.done(current, "Исходный ответ взят из заранее подготовленного демонстрационного сценария. "
                             "Это не генерация языковой модели.", method="demo_scenario")
            run.provider, run.model = None, None
        elif run.answer_origin == "user":
            tr.start(current, "user_provided")
            tr.done(current, "Исходный ответ вставлен пользователем для проверки. Генерация не выполнялась.",
                    method="user_provided")
            run.provider, run.model = None, None
        else:
            tr.start(current, "llm", slow=True)
            sources = None
            if docs_to_llm:
                hits = retrieval.search(db, bank_id=run.bank_id, product_id=run.product_id, query=run.question, top_k=5)
                sources = [{"sid": f"s{i}", "title": h.doc.title, "section": h.section, "actuality": h.doc.actuality,
                            "text": h.text} for i, h in enumerate([h for h in hits if not h.suspicious], 1)]
            try:
                routed = await router.complete("generation", generation_messages(
                    run.question, product.name if product else None, sources), preference=preference,
                    quality=quality, temperature=0.3, max_tokens=700)
            except ProviderError as exc:
                ai_calls.extend(a.to_dict() for a in getattr(exc, "attempts", []))
                run.ai_calls = ai_calls
                raise
            account(routed)
            run.original_answer = routed.result.text
            run.provider, run.model = routed.result.provider, routed.result.model
            tr.done(current, f"Ответ сгенерирован: {routed.result.provider} / {routed.result.model}, "
                             f"{routed.result.latency_ms} мс" + (" (с контекстом из базы знаний)" if sources else
                                                                  " (документы банка в модель не передавались)"),
                    method=f"llm:{routed.result.provider}")
        answer = run.original_answer or ""

        # 2-3. CLAIMS + RETRIEVAL ---------------------------------------
        current = "claim_extraction"
        tr.start(current, "deterministic: предложения + парсер фактов")
        analyzed = analyze(db, bank_id=run.bank_id, product_id=run.product_id, question=run.question, answer=answer)
        substantive = [a for a in analyzed if a.claim.substantive]
        tr.done(current, f"Найдено утверждений: {len(analyzed)}, из них проверяемых: {len(substantive)}")

        current = "source_retrieval"
        tr.start(current, "BM25 по базе знаний банка + общие нормативные источники")
        chunk_ids = {h.chunk_id for a in substantive for h in a.hits}
        doc_ids = {h.doc.id for a in substantive for h in a.hits}
        warn = []
        if substantive and not chunk_ids:
            warn.append("Релевантные источники не найдены — утверждения не могут быть подтверждены")
        tr.done(current, f"Фрагментов: {len(chunk_ids)}, документов: {len(doc_ids)}", warnings=warn)

        # 4. LEGAL VERIFICATION -------------------------------------------
        current = "legal_verification"
        method = "deterministic evidence engine"
        tr.start(current, method, slow=run.mode == "live" and docs_to_llm)
        v_warn: list[str] = []
        if run.mode == "live" and substantive:
            if not docs_to_llm:
                v_warn.append("Передача документов банка во внешнюю модель отключена в настройках — "
                              "LLM-верификация не выполнялась, использована только доказательная проверка.")
            else:
                src, by_sid = _sources_for_llm(substantive)
                if src:
                    try:
                        routed = await router.complete("legal_verification", verification_messages(
                            run.question, [{"id": a.claim.id, "text": a.claim.text} for a in substantive], src),
                            preference=preference, quality=quality, json_mode=True, temperature=0.0, max_tokens=1200)
                        account(routed)
                        judgements = _validate_llm_judgements(parse_json_object(routed.result.text), by_sid)
                        if not judgements:
                            v_warn.append("Ответ модели-верификатора не прошёл валидацию JSON — использована "
                                          "только доказательная проверка.")
                        merge_llm(analyzed, judgements)
                        method = f"deterministic + llm:{routed.result.provider}"
                    except ProviderError as exc:
                        ai_calls.extend(a.to_dict() for a in getattr(exc, "attempts", []))
                        v_warn.append(f"LLM-верификация недоступна ({exc.code}) — использована только "
                                      "доказательная проверка.")
        legal = finalize(run.question, answer, analyzed)
        counts: dict[str, int] = {}
        for c in legal.claims:
            if c.claim.substantive:
                counts[c.status] = counts.get(c.status, 0) + 1
        tr.done(current, "; ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "Проверяемых утверждений нет",
                method=method, warnings=v_warn)

        # 5. LEGAL CORRECTION --------------------------------------------
        current = "legal_correction"
        tr.start(current, "пропорциональная политика рисков")
        run.legal_answer = legal.corrected_text
        run.claims = [c.to_dict() for c in legal.claims]
        run.sources = legal.sources
        run.legal_changes = legal.changes
        run.missing_data = legal.missing_data
        run.max_risk = legal.max_risk
        tr.done(current, f"Изменений: {len(legal.changes)}" + (f"; требует проверки: {len(legal.review_reasons)}"
                                                               if legal.review_reasons else ""))

        # 6-7. LINGUISTIC + SEMANTIC --------------------------------------
        current = "linguistic_rewrite"
        tone = run.tone if run.tone in TONES else "neutral"
        tr.start(current, slow=run.mode == "live")
        candidate, ling_method, ling_changes, l_warn = None, None, [], []
        attempts_log = []
        if run.mode == "live":
            try:
                routed = await router.complete("linguistic_rewrite", rewrite_messages(legal.corrected_text, tone),
                                               preference=preference, quality=quality, temperature=0.3, max_tokens=900)
                account(routed)
                candidate, ling_method = routed.result.text, f"llm:{routed.result.provider}"
                ling_changes = [{"type": "llm_rewrite", "description": f"Переписано моделью {routed.result.model}"}]
            except ProviderError as exc:
                ai_calls.extend(a.to_dict() for a in getattr(exc, "attempts", []))
                l_warn.append(f"LLM-редактор недоступен ({exc.code}) — использован офлайн-редактор.")
        det = rewrite(legal.corrected_text, tone=tone)
        if candidate is None:
            candidate, ling_method, ling_changes = det.text, det.method, det.changes
        tr.done(current, f"Тон: {TONES[tone]}; изменений стиля: {len(ling_changes)}", method=ling_method,
                warnings=l_warn)

        current = "semantic_validation"
        tr.start(current, "сверка фактов, отрицаний, условий и оговорок")
        check = validate(legal.corrected_text, candidate)
        attempts_log.append({"method": ling_method, "passed": check["passed"]})
        final, fallback_used = candidate, None
        if not check["passed"] and ling_method != det.method:
            det_check = validate(legal.corrected_text, det.text)
            attempts_log.append({"method": det.method, "passed": det_check["passed"]})
            if det_check["passed"]:
                final, check, fallback_used = det.text, det_check, "offline_rewriter"
                ling_changes = det.changes
        if not check["passed"]:
            final, fallback_used = legal.corrected_text, "legal_text"
            check = {**validate(legal.corrected_text, final), "note": "Упрощённая версия изменила смысл — "
                     "клиенту отдан юридически скорректированный текст без упрощения."}
        check["attempts"] = attempts_log
        check["fallback"] = fallback_used
        run.semantic_check = check
        run.linguistic = {"tone": tone, "tone_label": TONES[tone], "method": ling_method, "changes": ling_changes,
                          "candidate": candidate if fallback_used else None, "fallback": fallback_used}
        tr.done(current, "Смысл сохранён" if not fallback_used else
                f"Обнаружено изменение смысла — откат ({fallback_used})",
                warnings=["Первая версия упрощения отклонена проверкой смысла"] if fallback_used else [])

        # 8. FINAL ----------------------------------------------------------
        current = "final_response"
        tr.start(current)
        run.final_answer = final
        run.result_status = "NEEDS_REVIEW" if legal.needs_review else "READY"
        notices = []
        if run.mode == "demo":
            notices.append("DEMO MODE: исходный ответ не сгенерирован моделью; юридический и лингвистический "
                           "слои выполнены по демонстрационной базе знаний.")
        if not any(s.get("actuality") == "current" for s in legal.sources) and substantive:
            notices.append("Ни одно утверждение не подтверждено действующим источником: SafeTone не заявляет о "
                           "проверке по действующему законодательству.")
        notices.extend(legal.review_reasons)
        run.notices = notices
        tr.done(current, "Готово к отправке клиенту" if run.result_status == "READY" else
                "Черновик подготовлен, требуется ручная проверка")
        run.execution_status = "completed"
    except Exception as exc:  # noqa: BLE001 — any failure must be recorded as FAILED
        if isinstance(exc, AppError):
            err = {"code": exc.code, "message": exc.message, "stage": current}
        else:
            log.exception("Pipeline crashed at stage %s", current)
            err = {"code": "PIPELINE_ERROR", "message": "Внутренняя ошибка обработки", "stage": current}
        db.rollback()
        run = db.get(ProcessingRun, run.id)
        tr.run = run
        tr.fail_rest(current, err["message"])
        run.error = err
        run.execution_status = "failed"
        run.result_status = "FAILED"
        run.final_answer = None
    finally:
        run.ai_calls = ai_calls
        run.tokens_total = tokens_total or None
        run.cost_estimate = cost_total
        run.duration_ms = int((time.perf_counter() - t_start) * 1000)
        run.finished_at = _now()
        db.commit()


__all__ = ["execute_run", "initial_stages", "STAGES", "max_risk"]
