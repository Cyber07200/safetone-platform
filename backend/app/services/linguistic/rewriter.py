"""Deterministic plain-language rewriter (Linguistic Clarity Engine, offline).

It works with a style dictionary: bureaucratic phrase -> plain phrase.
Every rule is meaning-preserving by construction (it never touches
numbers, negations or conditions); the semantic validator double-checks
the result anyway. Used in Demo Mode and as a fallback in Live Mode.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.knowledge.text import split_sentences
from app.services.legal.policy import (CAUTION_ACTUALITY, CAUTION_LEGAL, CAUTION_MEDIUM, CAUTION_UNVERIFIED)

TONES = {
    "neutral": "Нейтральный банковский",
    "friendly": "Дружелюбный",
    "concise": "Краткий и деловой",
    "detailed": "Подробное объяснение",
}

CAUTIONS = (CAUTION_UNVERIFIED, CAUTION_ACTUALITY, CAUTION_LEGAL, CAUTION_MEDIUM)

# (pattern, replacement, human-readable description)
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\bВ целях осуществления процедуры\s+", re.I), "Для ", "«В целях осуществления процедуры» → «Для»"),
    (re.compile(r"\bв целях\b", re.I), "для", "«в целях» → «для»"),
    (re.compile(r"\b[Кк]лиенту надлежит осуществить подачу заявления\b"), "нужно подать заявление",
     "«Клиенту надлежит осуществить подачу заявления» → «нужно подать заявление»"),
    (re.compile(r"\bосуществить подачу заявления\b", re.I), "подать заявление",
     "«осуществить подачу заявления» → «подать заявление»"),
    (re.compile(r"\b[Кк]лиенту надлежит\b"), "нужно", "«Клиенту надлежит» → «нужно»"),
    (re.compile(r"\bнадлежит\b", re.I), "нужно", "«надлежит» → «нужно»"),
    (re.compile(r"\bнеобходимо осуществить\b", re.I), "нужно", "«необходимо осуществить» → «нужно»"),
    (re.compile(r"\bденежных средств\b"), "денег", "«денежных средств» → «денег»"),
    (re.compile(r"\bденежные средства\b"), "деньги", "«денежные средства» → «деньги»"),
    (re.compile(r"\bв соответствии с\b", re.I), "по", "«в соответствии с» → «по»"),
    (re.compile(r"\bв случае,? если\b", re.I), "если", "«в случае, если» → «если»"),
    (re.compile(r"\bпо реквизитам, указанным [Кк]лиентом в заявлении\b"), "по реквизитам, которые вы укажете в заявлении",
     "«указанным Клиентом» → «которые вы укажете»"),
    (re.compile(r"\bсо дня получения заявления\b"), "со дня, когда банк получит заявление",
     "«со дня получения заявления» → «со дня, когда банк получит заявление»"),
    (re.compile(r"\b[Бб]анк самостоятельно сообщает в налоговый орган\b"), "Банк сам сообщит в налоговую",
     "«самостоятельно сообщает в налоговый орган» → «сам сообщит в налоговую»"),
    (re.compile(r"\b[Кк]лиенту не требуется уведомлять налоговый орган\b"), "Вам не нужно сообщать в налоговую",
     "«Клиенту не требуется уведомлять налоговый орган» → «Вам не нужно сообщать в налоговую»"),
    (re.compile(r"\bЗа[её]мщик вправе\b"), "Вы можете", "«Заёмщик вправе» → «Вы можете»"),
    (re.compile(r"\bЗа[её]мщик подаёт\b"), "вы подаёте", "«Заёмщик подаёт» → «вы подаёте»"),
    (re.compile(r"\bЗа[её]мщик выбирает\b"), "вы выбираете", "«Заёмщик выбирает» → «вы выбираете»"),
    (re.compile(r"\bбез предварительного уведомления Банка\b"), "без предварительного уведомления банка",
     "«Банка» → «банка»"),
    (re.compile(r"\b(Банк|банк) не вправе\b"), r"\1 не может", "«не вправе» → «не может»"),
    (re.compile(r"\b(Банк|банк) вправе\b"), r"\1 может", "«вправе» → «может»"),
    (re.compile(r"\bи вправе\b"), "и может", "«вправе» → «может»"),
    (re.compile(r"\bпроизводится\b"), "проводится", "«производится» → «проводится»"),
    (re.compile(r"(?<=[а-яё,] )Банк(а|у|ом|е)?\b"), r"банк\1", "«Банк» в середине фразы → «банк»"),
]

_COURTESY = re.compile(r"^(здравствуйте|добрый (день|вечер|утро)|если у вас (остались|появятся|есть) вопросы|"
                       r"обращайтесь|хорошего дня|всего доброго|рад[аы]? помочь)", re.I)

_FRIENDLY_CLOSING = "Если появятся вопросы — напишите, я помогу."


@dataclass
class RewriteResult:
    text: str
    changes: list[dict] = field(default_factory=list)
    method: str = "deterministic-style-dictionary"


def _split_body_and_cautions(text: str) -> tuple[str, list[str]]:
    cautions = [c for c in CAUTIONS if c in text]
    body = text
    for c in cautions:
        body = body.replace(c, "")
    return body.strip(), cautions


def _split_long(sentence: str, changes: list[dict]) -> list[str]:
    if len(sentence.split()) <= 28:
        return [sentence]
    m = re.search(r";\s+|,\s+а также\s+", sentence)
    if not m:
        return [sentence]
    first = sentence[:m.start()].rstrip(",; ") + "."
    rest = sentence[m.end():].strip()
    rest = rest[:1].upper() + rest[1:]
    changes.append({"type": "split_sentence", "description": "Длинное предложение разделено на два"})
    return [first] + _split_long(rest, changes)


def rewrite(text: str, *, tone: str = "neutral") -> RewriteResult:
    body, cautions = _split_body_and_cautions(text)
    changes: list[dict] = []
    for pat, repl, descr in _RULES:
        new, n = pat.subn(repl, body)
        if n:
            changes.append({"type": "plain_language", "description": descr, "count": n})
            body = new

    sentences: list[str] = []
    for s in split_sentences(body):
        sentences.extend(_split_long(s, changes))
    sentences = [s[:1].upper() + s[1:] if s else s for s in sentences]

    if tone == "concise":
        kept = [s for s in sentences if not _COURTESY.search(s)]
        if len(kept) != len(sentences):
            changes.append({"type": "tone", "description": "Убраны вежливые вводные и заключительные фразы"})
        sentences = kept or sentences
    elif tone == "friendly":
        if not any(_COURTESY.search(s) for s in sentences[-1:]):
            sentences.append(_FRIENDLY_CLOSING)
            changes.append({"type": "tone", "description": "Добавлена дружелюбная заключительная фраза (без фактов)"})

    if tone == "detailed" and len(sentences) >= 3:
        lead, items = sentences[0], sentences[1:]
        out = lead + "\n\n" + "\n".join(f"• {s}" for s in items)
        changes.append({"type": "structure", "description": "Ответ структурирован списком"})
    else:
        out = " ".join(sentences)

    if cautions:
        label = "Важно: " if tone == "detailed" else ""
        out = out + "\n\n" + "\n".join(label + c for c in cautions)
    return RewriteResult(out.strip(), changes)
