"""Semantic preservation check: final text vs legally corrected text.

The check is deliberately conservative. It verifies that every
significant element of the legally corrected answer survived the
rewrite: amounts/rates/terms, negations, conditions and limitations,
explicit uncertainty, quoted product names — and that no new numbers or
promises appeared.
"""
from __future__ import annotations

import re
from collections import Counter

from app.services.knowledge.facts import extract_mentions
from app.services.knowledge.text import content_terms, split_sentences, tokens
from app.services.legal.claims import _COMMITMENT  # same definition as the legal layer
from .rewriter import CAUTIONS

_NEG = {"не", "нет", "без", "нельзя", "ни", "невозможно"}
_CONDITIONS = ["если", "только", "кроме", "за исключением", "при условии", "не позднее", "не менее",
               "не более", "до", "от", "в течение"]
_HEDGES = ["уточните", "не могу подтвердить", "может", "могут", "требует", "специалист"]


def _facts(text: str) -> Counter:
    c: Counter = Counter()
    for s in split_sentences(text):
        for m in extract_mentions(s):
            c[(m.unit, round(m.value, 4))] += 1
    return c


def _count_phrase(text: str, phrase: str) -> int:
    return len(re.findall(r"(?<![а-яё])" + re.escape(phrase) + r"(?![а-яё])", text.lower()))


def _fmt(key) -> str:
    unit, value = key
    names = {"percent": "%", "rub": " ₽", "days": " дн.", "workdays": " раб. дн.", "months": " мес.",
             "fee_zero": " (без комиссии)"}
    v = f"{value:g}".replace(".", ",")
    return ("без комиссии" if unit == "fee_zero" else v + names.get(unit, ""))


def validate(legal_text: str, final_text: str) -> dict:
    checks = []

    f_legal, f_final = _facts(legal_text), _facts(final_text)
    lost = f_legal - f_final
    added = f_final - f_legal
    checks.append({"name": "numbers_preserved", "title": "Суммы, ставки и сроки сохранены",
                   "passed": not lost,
                   "detail": "Все значения на месте" if not lost else
                   "Потеряны: " + ", ".join(_fmt(k) for k in lost)})
    checks.append({"name": "no_new_numbers", "title": "Не добавлено новых значений",
                   "passed": not added,
                   "detail": "Новых значений нет" if not added else
                   "Добавлены: " + ", ".join(_fmt(k) for k in added)})

    neg_l = sum(1 for t in tokens(legal_text) if t in _NEG)
    neg_f = sum(1 for t in tokens(final_text) if t in _NEG)
    checks.append({"name": "negations_preserved", "title": "Отрицания и запреты сохранены",
                   "passed": neg_f == neg_l,
                   "detail": f"Отрицаний: было {neg_l}, стало {neg_f}"})

    missing_conditions = [p for p in _CONDITIONS if _count_phrase(final_text, p) < _count_phrase(legal_text, p)]
    checks.append({"name": "conditions_preserved", "title": "Условия, исключения и ограничения сохранены",
                   "passed": not missing_conditions,
                   "detail": "Сохранены" if not missing_conditions else
                   "Пропали: " + ", ".join(f"«{p}»" for p in missing_conditions)})

    missing_cautions = [c for c in CAUTIONS if c in legal_text and c not in final_text]
    weaker = [h for h in _HEDGES if _count_phrase(final_text, h) < _count_phrase(legal_text, h)]
    checks.append({"name": "uncertainty_preserved", "title": "Неопределённость не усилена до уверенности",
                   "passed": not missing_cautions and not weaker,
                   "detail": "Оговорки сохранены" if not (missing_cautions or weaker) else
                   "Ослаблены оговорки: " + ", ".join(f"«{h}»" for h in weaker) +
                   (" · удалено предупреждение юридического слоя" if missing_cautions else "")})

    new_promises = len(_COMMITMENT.findall(final_text)) > len(_COMMITMENT.findall(legal_text))
    checks.append({"name": "no_new_promises", "title": "Не добавлено новых обещаний",
                   "passed": not new_promises,
                   "detail": "Новых обещаний нет" if not new_promises else "Появилась формулировка-обещание"})

    names_l = set(re.findall(r"«[^»]+»", legal_text))
    names_f = set(re.findall(r"«[^»]+»", final_text))
    lost_names = names_l - names_f
    checks.append({"name": "names_preserved", "title": "Названия продуктов и разделов сохранены",
                   "passed": not lost_names,
                   "detail": "Сохранены" if not lost_names else "Пропали: " + ", ".join(sorted(lost_names))})

    tl, tf = set(content_terms(legal_text)), set(content_terms(final_text))
    overlap = len(tl & tf) / len(tl) if tl else 1.0
    return {
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "term_overlap": round(overlap, 3),
    }
