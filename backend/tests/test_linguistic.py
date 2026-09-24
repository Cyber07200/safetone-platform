"""Linguistic Clarity Engine and semantic preservation (mandatory scenario 6)."""
from __future__ import annotations

import pytest

from app.services.legal.policy import CAUTION_UNVERIFIED
from app.services.linguistic.rewriter import rewrite
from app.services.linguistic.semantic import validate

LEGAL = ("В целях осуществления процедуры закрытия расчётного счёта Клиенту надлежит осуществить подачу "
         "заявления о закрытии счёта в интернет-банке или в офисе Банка. Остаток денежных средств перечисляется "
         "по реквизитам, указанным Клиентом в заявлении, не позднее 7 рабочих дней со дня получения заявления.")


@pytest.mark.parametrize("tone", ["neutral", "friendly", "concise", "detailed"])
def test_rewrite_keeps_essential_terms_for_every_tone(tone):
    res = rewrite(LEGAL, tone=tone)
    assert "7 рабочих дней" in res.text
    assert "не позднее" in res.text
    assert "надлежит" not in res.text and "денежных средств" not in res.text
    assert validate(LEGAL, res.text)["passed"]


def test_rewrite_records_changes():
    res = rewrite(LEGAL)
    kinds = {c["description"] for c in res.changes}
    assert any("надлежит" in k for k in kinds)


def test_cautions_are_preserved_verbatim():
    text = "Минимальная сумма вклада — 10 000 ₽.\n\n" + CAUTION_UNVERIFIED
    res = rewrite(text, tone="detailed")
    assert CAUTION_UNVERIFIED in res.text
    assert validate(text, res.text)["passed"]


def _failed(check, name):
    return next(c for c in check["checks"] if c["name"] == name)["passed"] is False


def test_validator_detects_changed_number():
    assert _failed(validate("Ставка — 29,9% годовых.", "Ставка — 19,9% годовых."), "numbers_preserved")


def test_validator_detects_lost_negation():
    assert _failed(validate("Льготный период не распространяется на снятие наличных.",
                            "Льготный период распространяется на снятие наличных."), "negations_preserved")


def test_validator_detects_lost_condition():
    assert _failed(validate("Обслуживание бесплатно, если сумма покупок от 10 000 ₽.",
                            "Обслуживание бесплатно, сумма покупок 10 000 ₽."), "conditions_preserved")


def test_validator_detects_new_promise():
    assert _failed(validate("Банк рассматривает заявку.", "Банк гарантирует одобрение заявки."), "no_new_promises")


def test_validator_detects_removed_caution():
    legal = "Минимальная сумма — 10 000 ₽.\n\n" + CAUTION_UNVERIFIED
    assert _failed(validate(legal, "Минимальная сумма — 10 000 ₽."), "uncertainty_preserved")


def test_validator_detects_added_number():
    assert _failed(validate("Открытие счёта — без комиссии.", "Открытие счёта — без комиссии, за 1 день."),
                   "no_new_numbers")
