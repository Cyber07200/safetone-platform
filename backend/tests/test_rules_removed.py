"""Regression: the legacy `guidelines.py` keyword rules are gone from the
production path and harmless answers that used to be blocked now pass."""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

from app.services.legal.engine import run_legal

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def test_guidelines_module_does_not_exist():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("guidelines")
    assert not list(APP_DIR.rglob("guidelines*.py"))


def test_no_code_references_legacy_rules():
    pattern = re.compile(r"\bcheck_text\b|\bRULES\s*=|safe_reply|BLOCKED_L1|BLOCKED_L2|from guidelines")
    offenders = [p for p in APP_DIR.rglob("*.py") if pattern.search(p.read_text("utf-8"))]
    assert offenders == []


# Phrases that were keywords of the old rules (rule #2 "без оплаты", #11
# "не нужно подписывать", #21 "доходность") inside perfectly harmless answers.
@pytest.mark.parametrize("answer", [
    "Выписку по счёту карты можно получить без оплаты в мобильном приложении.",
    "Выписка по счёту карты в мобильном приложении и интернет-банке — без комиссии.",
    "Перевыпуск карты по окончании срока её действия — без комиссии.",
])
def test_previously_blocked_harmless_answers_now_pass(db, bank_id, products, answer):
    r = run_legal(db, bank_id=bank_id, product_id=products["card-horizon-120"],
                  question="Сколько стоит выписка?", answer=answer)
    assert not r.needs_review
    assert r.corrected_text == answer
    assert all(c.status == "CONFIRMED" for c in r.claims if c.claim.substantive)


def test_legal_term_alone_is_not_a_violation(db, bank_id, products):
    # "гарантия", "договор", "неустойка" are just words — only unsupported claims matter
    answer = "За просрочку ежемесячного платежа начисляется неустойка 20% годовых на сумму просроченной задолженности."
    r = run_legal(db, bank_id=bank_id, product_id=products["loan-prostoy"], question="Есть ли неустойка?",
                  answer=answer)
    assert not r.needs_review and r.corrected_text == answer


def test_unmatched_harmless_statement_is_not_blocked(db, bank_id, products):
    # no source mentions this, but it is low-risk informational text: kept, not blocked
    answer = "Мобильное приложение удобно использовать с телефона."
    r = run_legal(db, bank_id=bank_id, product_id=products["card-horizon-120"], question="Приложение?",
                  answer=answer)
    assert r.corrected_text == answer
    assert not r.needs_review
