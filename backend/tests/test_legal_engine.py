"""Legal Assurance Engine — unit and regression tests (mandatory scenarios 1–5, 9)."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import Document
from app.services.demo.scenarios import BY_ID, SCENARIOS
from app.services.legal.claims import extract_claims, is_legal_interpretation_question
from app.services.legal.engine import run_legal
from app.services.knowledge.retrieval import effective_actuality


def legal(db, bank_id, products, product_code, question, answer):
    return run_legal(db, bank_id=bank_id, product_id=products.get(product_code), question=question, answer=answer)


def substantive(outcome):
    return [c for c in outcome.claims if c.claim.substantive]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
def test_every_demo_scenario_reaches_designed_status(db, bank_id, products, scenario):
    r = legal(db, bank_id, products, scenario.product_code, scenario.question, scenario.answer)
    status = "NEEDS_REVIEW" if r.needs_review else "READY"
    assert status == scenario.expected_status, r.review_reasons


# 1. Безопасный ответ не блокируется ------------------------------------------------
@pytest.mark.parametrize("answer", [
    BY_ID["safe-balance"].answer,
    "Доступный баланс карты можно запросить в банкомате Банка, выбрав пункт «Баланс».",
    "Выписка по счёту карты в мобильном приложении и интернет-банке — без комиссии.",
    "Здравствуйте! Спасибо за обращение. Если у вас остались вопросы — обращайтесь!",
])
def test_safe_answer_is_not_blocked(db, bank_id, products, answer):
    r = legal(db, bank_id, products, "card-horizon-120", "Как узнать баланс карты?", answer)
    assert not r.needs_review
    assert r.corrected_text == answer.strip()          # nothing changed
    assert r.changes == []
    assert all(c.status == "CONFIRMED" for c in substantive(r))


# 2. Корректная информация из договора сохраняется ----------------------------------
def test_correct_contract_information_is_preserved(db, bank_id, products):
    answer = ("Заёмщик вправе досрочно погасить кредит полностью или частично в любой день без комиссии. "
              "За просрочку ежемесячного платежа начисляется неустойка 20% годовых на сумму просроченной задолженности.")
    r = legal(db, bank_id, products, "loan-prostoy", "Условия досрочного погашения?", answer)
    assert r.corrected_text == answer
    assert [c.status for c in substantive(r)] == ["CONFIRMED", "CONFIRMED"]
    assert all(c.verdict.evidence and c.verdict.evidence[0].sentence.hit.doc.actuality == "current"
               for c in substantive(r))


# 3. Неверная ставка исправляется только при наличии подтверждённого источника --------
def test_wrong_rate_is_corrected_from_current_source(db, bank_id, products):
    sc = BY_ID["rate-error"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    c1 = substantive(r)[0]
    assert c1.status == "CONTRADICTED" and c1.action == "corrected"
    assert "29,9%" in r.corrected_text and "19,9%" not in r.corrected_text
    ev = c1.verdict.evidence[0]
    assert ev.relation == "contradicts" and ev.source_value == "29,9%"
    assert "Тарифы по кредитной карте" in ev.sentence.hit.doc.title
    assert r.changes[0]["basis"], "correction must reference its legal basis"


def test_wrong_rate_is_not_corrected_without_source(db, other_bank_id):
    # the isolation bank has no documents at all -> nothing to correct from
    r = run_legal(db, bank_id=other_bank_id, product_id=None, question="Ставка по карте?",
                  answer="Процентная ставка по операциям покупок составляет 19,9% годовых.")
    c1 = substantive(r)[0]
    assert c1.status == "UNVERIFIED"
    assert c1.action == "removed"
    assert "29,9" not in r.corrected_text and "19,9" not in r.corrected_text
    assert r.needs_review


# 4. Отсутствие источника не приводит к выдумыванию условий --------------------------
def test_missing_source_does_not_invent_conditions(db, bank_id, products):
    sc = BY_ID["incomplete-data"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    first = substantive(r)[0]
    assert first.status == "UNVERIFIED"
    assert "16%" not in r.corrected_text
    # no rate from other terms (14% / 12,5%) is substituted for 24 months
    assert "14%" not in r.corrected_text and "12,5%" not in r.corrected_text
    assert r.missing_data and "24 месяца" in r.missing_data[0]
    assert "10 000 ₽" in r.corrected_text            # the confirmed part is kept
    assert r.needs_review


# 5. Неоднозначный юридический вопрос — осторожная обработка -------------------------
def test_ambiguous_legal_question_is_handled_cautiously(db, bank_id, products):
    sc = BY_ID["ambiguous-legal"]
    assert is_legal_interpretation_question(sc.question)
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    assert r.needs_review
    assert all(c.status == "NEEDS_REVIEW" for c in substantive(r))
    assert "никогда" not in r.corrected_text
    assert "суд" not in r.corrected_text.lower()
    assert "за исключением" in r.corrected_text       # grounded exception from the contract
    assert "специалист" in r.corrected_text


def test_critical_promise_requires_review_even_after_correction(db, bank_id, products):
    sc = BY_ID["critical-guarantee"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    assert r.max_risk == "CRITICAL"
    assert r.needs_review
    assert "гарантируем" not in r.corrected_text
    assert "не гарантирует одобрение" in r.corrected_text


def test_fee_claim_contradicting_tariff_replaced_with_tariff_wording(db, bank_id, products):
    sc = BY_ID["fee-error"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    assert "3,9% от суммы + 390 ₽" in r.corrected_text
    assert "не распространяется" in r.corrected_text
    assert not r.needs_review


def test_partial_contradiction_keeps_confirmed_part(db, bank_id, products):
    sc = BY_ID["contract-conflict"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    statuses = [c.status for c in substantive(r)]
    assert statuses == ["CONFIRMED", "CONTRADICTED", "CONTRADICTED"]
    assert r.corrected_text.startswith("Да, кредит можно погасить досрочно.")
    assert "1 день" in r.corrected_text and "30 дней" not in r.corrected_text
    assert "2%" not in r.corrected_text


# 9. Устаревший документ не считается автоматически актуальным ------------------------
def test_superseded_tariff_is_not_treated_as_current(db, bank_id, products):
    sc = BY_ID["outdated-tariff"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    c = substantive(r)[0]
    assert c.status == "CONTRADICTED"
    assert "690 ₽" in r.corrected_text
    rel = {e.relation: e for e in c.verdict.evidence}
    assert rel["matches_outdated"].sentence.hit.doc.actuality == "superseded"
    assert rel["contradicts"].sentence.hit.doc.actuality == "current"


def test_unverified_law_excerpt_gives_outdated_source(db, bank_id, products):
    sc = BY_ID["unverified-law"]
    r = legal(db, bank_id, products, sc.product_code, sc.question, sc.answer)
    assert {c.status for c in substantive(r)} == {"OUTDATED_SOURCE"}
    assert "актуальность которого не подтверждена" in r.corrected_text


def test_effective_actuality_uses_dates_not_upload_time():
    today = date(2026, 9, 24)
    d = Document(actuality_status="current", effective_from=today - timedelta(days=10),
                 effective_to=today - timedelta(days=1))
    assert effective_actuality(d, today) == "expired"
    d = Document(actuality_status="current", effective_from=today + timedelta(days=5))
    assert effective_actuality(d, today) == "not_yet_effective"
    assert effective_actuality(Document(actuality_status="unverified"), today) == "unverified"
    assert effective_actuality(Document(actuality_status="superseded"), today) == "superseded"
    assert effective_actuality(Document(actuality_status="current"), today) == "current"


def test_claim_extraction_marks_courtesy_as_non_substantive():
    claims = extract_claims("Здравствуйте! Ставка по вкладу — 14% годовых. Чем ещё могу помочь?")
    assert [c.substantive for c in claims] == [False, True, False]
    assert claims[1].verifiable_mentions[0].value == 14


def test_duration_next_to_rate_is_a_condition_not_a_claim():
    c = extract_claims("Ставка по вкладу на срок 6 месяцев — 14% годовых.")[0]
    assert [m.unit for m in c.verifiable_mentions] == ["percent"]
    assert [m.unit for m in c.conditions] == ["months"]
