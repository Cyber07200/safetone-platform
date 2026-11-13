"""Regression: a rate and a fee joined by «плюс»/«и» in one sentence are two
facts. Found in a live GigaChat run: the correct cash rate 49,9% was marked
CONTRADICTED and «corrected» to the cash-withdrawal fee 3,9%."""
from app.services.knowledge.facts import extract_mentions
from tests.conftest import process

ANSWER = ("На покупки льготный период до 120 дней без процентов. При снятии наличных процентная ставка "
          "составляет 49,9% годовых плюс комиссия 3,9% от суммы + 390 ₽.")


def test_rate_and_fee_joined_by_plus_get_separate_topics():
    rate, fee, fixed = extract_mentions(
        "При снятии наличных процентная ставка составляет 49,9% годовых плюс комиссия 3,9% от суммы + 390 ₽.")
    assert "rate" in rate.topics and "fee" not in rate.topics
    assert "fee" in fee.topics and "rate" not in fee.topics
    assert "cash" in rate.topics and "cash" in fee.topics  # the case scopes both facts
    assert "fee" in fixed.topics


def test_plus_inside_one_fee_is_not_split():
    pct, fixed = extract_mentions("Комиссия за снятие наличных — 3,9% от суммы плюс 390 ₽.")
    assert pct.topics == fixed.topics


def test_correct_cash_rate_is_not_replaced_by_fee(client, bank_id, products):
    r = process(client, bank_id, question="Ставка и комиссия за снятие наличных по карте «Берег 120»?",
                answer_text=ANSWER, product_id=products["card-bereg-120"])
    assert r.status_code == 200, r.text
    run = r.json()
    assert "3,9% годовых" not in (run["final_answer"] or "")
    assert "49,9%" in run["final_answer"]
    assert not [c for c in run["claims"] if c["status"] == "CONTRADICTED"]
