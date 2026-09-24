"""Extraction of verifiable facts from text.

Parses quantitative mentions (rates, fees, durations, amounts) together
with the *topic* they refer to, so that a statement from an AI answer can
be compared with a statement in a bank document ("ставка по покупкам —
29,9% годовых" vs "ставка по покупкам 19,9%").

Topic lexicon here describes *what a number is about*. It is not a list of
forbidden phrases and never decides on its own that a text is unsafe.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import tokens

# topic -> (prefixes, excluded prefixes)
TOPICS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "rate": (("ставк", "годовых", "процентн"), ()),
    "fee": (("комисс", "плат", "стоимост", "стоит", "бесплатн", "взима"), ("платеж", "платёж", "платежн", "плательщ")),
    "grace": (("льготн", "беспроцентн"), ()),
    "limit": (("лимит",), ()),
    "penalty": (("неустойк", "штраф", "пен"), ("пенси",)),
    "minpay": (("минимальн",), ()),
    "cashback": (("кешбэк", "кэшбэк", "кешбек", "кэшбек"), ()),
    "term": (("срок",), ()),
    "compensation": (("возмещ", "страхов"), ()),
    # secondary / qualifier topics
    "cash": (("налич", "сняти", "снят", "банкомат"), ()),
    "service": (("обслуживан",), ()),
    "purchase": (("покуп",), ()),
    "transfer": (("перевод",), ()),
    "payment": (("платеж", "платёж"), ()),
    "overdue": (("просроч",), ()),
    "early": (("досрочн",), ()),
    "deposit": (("вклад", "депозит"), ()),
    "replenish": (("пополн",), ()),
    "insurance": (("страхов",), ()),
    "approval": (("одобр", "рассмотр"), ()),
    "history": (("истори",), ()),
    "statement": (("выписк",), ()),
    "sms": (("sms", "смс", "оповещ"), ()),
    "reissue": (("перевыпуск", "выпуск"), ()),
    "closing": (("закрыт", "закрыв"), ()),
    "notice": (("уведом", "заявлен"), ()),
    "rko": (("расчетн", "расчётн"), ()),
    "card": (("карт",), ()),
    "loan": (("кредит",), ("кредитн",)),
    "month_period": (("месяц", "ежемесячн"), ()),
}

PRIMARY_TOPICS = frozenset({"rate", "fee", "grace", "limit", "penalty", "minpay", "cashback", "term",
                            "compensation", "amount"})
FINANCIAL_TOPICS = PRIMARY_TOPICS | {"insurance", "approval", "early", "overdue", "deposit"}

_NUM = r"(\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,](\d+))?"
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("percent", re.compile(_NUM + r"\s*(?:%|процент(?:а|ов)?\b)", re.I)),
    ("rub_k", re.compile(_NUM + r"\s*(?:тыс\.?|тысяч\w*)\s*(?:₽|руб\w*\.?)", re.I)),
    ("rub_m", re.compile(_NUM + r"\s*(?:млн\.?|миллион\w*)\s*(?:₽|руб\w*\.?)", re.I)),
    ("rub", re.compile(_NUM + r"\s*(?:₽|руб(?:лей|ля|ль)?\.?(?![а-я]))", re.I)),
    ("workdays", re.compile(_NUM + r"\s*рабоч\w*\s+(?:дн\w*|день)", re.I)),
    ("days", re.compile(_NUM + r"\s*(?:календарн\w*\s+)?(?:дн(?:ей|я|ю)|день)\b", re.I)),
    ("months", re.compile(_NUM + r"\s*(?:мес(?:яц(?:а|ев)?)?\.?)(?![а-я])", re.I)),
    ("years", re.compile(_NUM + r"\s*(?:год(?:а)?|лет)\b(?!\w)", re.I)),
]
_ZERO_FEE = re.compile(
    r"без\s+(?:какой-либо\s+|дополнительной\s+)?(?:комисси\w*|оплат\w*|платы)|бесплатн\w*|не\s+взима\w*|комисси\w*\s+(?:не\s+(?:взимается|берется|берётся)|отсутствует)",
    re.I,
)
_UNIT_FAMILY = {"percent": "percent", "rub": "rub", "rub_k": "rub", "rub_m": "rub",
                "workdays": "workdays", "days": "days", "months": "months", "years": "months"}


@dataclass
class Mention:
    unit: str          # percent | rub | workdays | days | months | fee_zero
    value: float
    raw: str
    start: int
    end: int
    topics: frozenset[str] = field(default_factory=frozenset)

    @property
    def primary(self) -> frozenset[str]:
        return self.topics & PRIMARY_TOPICS

    def to_dict(self) -> dict:
        return {"unit": self.unit, "value": self.value, "raw": self.raw,
                "topics": sorted(self.topics)}


def topics_of(text: str) -> set[str]:
    found: set[str] = set()
    for tok in tokens(text):
        for topic, (prefixes, excluded) in TOPICS.items():
            if any(tok.startswith(p) for p in prefixes) and not any(tok.startswith(e) for e in excluded):
                found.add(topic)
    return found


def _to_float(int_part: str, frac: str | None) -> float:
    v = float(re.sub(r"[  ]", "", int_part))
    if frac:
        v += float("0." + frac)
    return v


def _clauses(sentence: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r";|,\s+(?!(?:но|а|и|или)?\s*(?:не\s+)?(?:менее|более|позднее|ранее)\b)|\s—\s(?=[а-яё]+\s(?:[а-яё]+\s)?[—–-])", sentence):
        spans.append((start, m.start()))
        start = m.end()
    spans.append((start, len(sentence)))
    return spans


def extract_mentions(sentence: str) -> list[Mention]:
    """All quantitative mentions of a single sentence with their topics."""
    sentence_topics = topics_of(sentence)
    sentence_primary = sentence_topics & PRIMARY_TOPICS
    taken: list[tuple[int, int]] = []
    mentions: list[Mention] = []

    def overlaps(a: int, b: int) -> bool:
        return any(a < e and b > s for s, e in taken)

    for kind, pat in _PATTERNS:
        for m in pat.finditer(sentence):
            if overlaps(m.start(), m.end()):
                continue
            value = _to_float(m.group(1), m.group(2))
            if kind == "rub_k":
                value *= 1_000
            elif kind == "rub_m":
                value *= 1_000_000
            elif kind == "years":
                value *= 12
            taken.append((m.start(), m.end()))
            mentions.append(Mention(_UNIT_FAMILY[kind], value, m.group(0).strip(), m.start(), m.end()))
    for m in _ZERO_FEE.finditer(sentence):
        if overlaps(m.start(), m.end()):
            continue
        taken.append((m.start(), m.end()))
        mentions.append(Mention("fee_zero", 0.0, m.group(0), m.start(), m.end()))

    # attach topics: clause-level topics, inheriting the sentence's primary topic
    # and — if the clause has no qualifier — qualifiers of preceding clauses
    # that carry no number of their own ("Снятие наличных, в т.ч. …, — 3%").
    clause_spans = _clauses(sentence)
    clause_has_mention = [any(s <= m.start < e for m in mentions) for s, e in clause_spans]
    for men in mentions:
        ci = next((i for i, (s, e) in enumerate(clause_spans) if s <= men.start < e), 0)
        cs, ce = clause_spans[ci]
        t = topics_of(sentence[cs:ce])
        if not (t - PRIMARY_TOPICS - _WEAK_QUALIFIERS):
            j = ci - 1
            while j >= 0 and not clause_has_mention[j]:
                t |= topics_of(sentence[clause_spans[j][0]:clause_spans[j][1]])
                j -= 1
        if not (t & PRIMARY_TOPICS):
            t |= sentence_primary
        if men.unit == "fee_zero":
            t.add("fee")
        if men.unit in ("rub", "fee_zero") and "service" in t:
            t.add("fee")
        if men.unit == "percent" and "годовых" in sentence[men.end:men.end + 12].lower():
            t.add("rate")
        if men.unit == "percent" and re.search(r"\bпод\s*$", sentence[max(0, men.start - 6):men.start], re.I):
            t.add("rate")
        if men.unit in ("days", "workdays", "months") and not (t & PRIMARY_TOPICS):
            t.add("term")
        if men.unit in ("rub", "percent") and not (t & PRIMARY_TOPICS):
            t.add("amount")
        men.topics = frozenset(t)
    mentions.sort(key=lambda x: x.start)
    return mentions


_WEAK_QUALIFIERS = frozenset({"card", "loan", "month_period", "payment"})


def units_compatible(a: Mention, b: Mention) -> bool:
    if a.unit == b.unit:
        return True
    zero = {a.unit, b.unit} & {"fee_zero"}
    if zero and ({a.unit, b.unit} - {"fee_zero"}) <= {"rub", "percent"}:
        return "fee" in a.topics and "fee" in b.topics
    return False


def topic_similarity(a: Mention, b: Mention) -> float:
    union = a.topics | b.topics
    if not union:
        return 0.0
    jac = len(a.topics & b.topics) / len(union)
    if a.primary & b.primary:
        return jac
    # "amount" = a number whose subject was not recognised: weak match only
    if "amount" in a.primary or "amount" in b.primary:
        return 0.5 * jac
    return 0.0


def secondary_conflict(a: Mention, b: Mention) -> bool:
    """Both mentions specify a qualifier (cash / purchase / service ...) and
    the qualifiers do not intersect -> they are about different things."""
    qa = a.topics - PRIMARY_TOPICS - _WEAK_QUALIFIERS
    qb = b.topics - PRIMARY_TOPICS - _WEAK_QUALIFIERS
    return bool(qa) and bool(qb) and not (qa & qb)


# Qualifiers that denote a special case of a product condition. A source value
# for a special case (early termination, overdue, cash...) must not be used to
# confirm or correct a general statement that does not mention that case.
SPECIAL_CASES = frozenset({"early", "overdue", "closing", "insurance", "cash", "transfer",
                           "replenish", "reissue", "sms", "statement", "penalty"})


def special_case_mismatch(claim: Mention, source: Mention) -> bool:
    return bool((source.topics & SPECIAL_CASES) - claim.topics)


def is_condition(m: Mention, sentence_mentions: list[Mention]) -> bool:
    """A duration stated next to a rate/fee ("на 6 месяцев — 14%") is a
    condition of that value, not a separate claim."""
    has_value = any(x.unit in ("percent", "rub", "fee_zero") for x in sentence_mentions)
    return has_value and m.unit in ("months", "days") and "grace" not in m.primary
