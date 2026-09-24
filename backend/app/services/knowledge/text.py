"""Russian text utilities: normalization, sentence splitting, stemming."""
from __future__ import annotations

import re
from functools import lru_cache

import snowballstemmer

_stemmer = snowballstemmer.stemmer("russian")

# Function words that carry no retrieval signal. This is a tokenizer
# stop-list, not a content filter: it never influences a legal decision.
STOPWORDS = frozenset("""
и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне
было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него
до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где есть надо ней для мы
тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж тогда кто этот того потому
этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда
можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много
разве три эту моя впрочем хорошо свою этой перед иногда лучше чуть том нельзя такой им более всегда
конечно всю между это также ваш ваша ваши вашей вашего вас нам наш наша наши который которая которые
которых который также либо каждый любой
""".split())

_WORD_RE = re.compile(r"[a-zа-яё0-9]+(?:[.,][0-9]+)?", re.I)
_SENT_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[А-ЯЁA-Z0-9«\"(•\-–])|\n+")


def normalize(text: str) -> str:
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


@lru_cache(maxsize=50_000)
def stem(word: str) -> str:
    w = word.lower().replace("ё", "е")
    if w.isdigit() or any(ch.isdigit() for ch in w):
        return w.replace(",", ".")
    return _stemmer.stemWord(w)


def tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text.replace("ё", "е").replace("Ё", "Е"))]


# Canonical stems for common banking synonyms / inflection families that
# the Snowball stemmer keeps apart. Used symmetrically for documents and
# queries, purely to improve matching.
_CANON = (
    (("увелич", "повыш", "повыс"), "увелич"),
    (("уменьш", "сниж", "сниз", "пониж", "пониз"), "уменьш"),
    (("погаш", "погас"), "погас"),
    (("одобр",), "одобр"),
    (("комисс",), "комисс"),
    (("сняти", "снят", "сним"), "снят"),
    (("взима", "взим"), "взим"),
    (("досрочн",), "досрочн"),
    (("заемщик", "заёмщик"), "заемщик"),
    (("кредитор",), "банк"),
)


def canon(stem_: str) -> str:
    for prefixes, target in _CANON:
        if stem_.startswith(prefixes):
            return target
    return stem_


def content_terms(text: str) -> list[str]:
    """Stemmed content tokens (no stop words, length >= 2)."""
    out = []
    for t in tokens(text):
        if t in STOPWORDS or (len(t) < 2 and not t.isdigit()):
            continue
        out.append(canon(stem(t)))
    return out


_ABBREV = {"п", "пп", "ст", "ч", "руб", "т", "г", "гг", "д", "тыс", "млн", "мин", "макс", "см", "прим",
           "т.е", "т.к", "т.д", "т.п", "др", "ул", "им", "№"}


def split_sentences(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for m in _SENT_SPLIT.finditer(text):
        if "\n" not in m.group(0):
            before = text[start:m.start()].rstrip()
            last = re.split(r"\s", before)[-1].rstrip(".").lower() if before else ""
            nxt = text[m.end():m.end() + 1]
            if last in _ABBREV and (nxt.isdigit() or nxt.islower()):
                continue  # "п. 4", "ст. 11" — not a sentence boundary
        seg = text[start:m.start()]
        start = m.end()
        s = seg.strip().lstrip("•-–— ").strip()
        if s:
            parts.append(s)
    s = text[start:].strip().lstrip("•-–— ").strip()
    if s:
        parts.append(s)
    return parts
