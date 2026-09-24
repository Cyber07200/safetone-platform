"""Claim extraction: split an AI answer into verifiable statements.

The flags below describe the *form* of a statement (a promise, an absolute
wording, a reference to law). They never make a decision by themselves:
they only calibrate the risk level of a claim that could not be confirmed
by sources, and they are shown in the audit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.knowledge.facts import FINANCIAL_TOPICS, Mention, extract_mentions, is_condition, topics_of
from app.services.knowledge.text import content_terms, split_sentences

_COURTESY = re.compile(
    r"^(здравствуйте|добрый (день|вечер|утро)|привет|спасибо|благодарим|рад[аы]? помочь|"
    r"если у вас (остались|появятся|есть) вопросы|чем (ещ[её] )?(я )?могу помочь|хорошего дня|"
    r"всего доброго|обращайтесь|надеюсь,? (это|мой ответ) помо)",
    re.I,
)
_COMMITMENT = re.compile(
    r"гарантир\w*|гарантия одобрен\w*|(точно|обязательно|стопроцентно|100\s*%)\s+одобр\w*|"
    r"одобр\w*\s+(гарантирован\w*|в любом случае|на 100\s*%)|без (какой-либо )?проверк\w*|без отказа",
    re.I,
)
_ABSOLUTE = re.compile(r"\b(никогда|всегда|ни при каких|в любых (обстоятельствах|случаях)|в любом случае|"
                       r"абсолютно|категорически)\b", re.I)
_LEGAL_REF = re.compile(r"\b(закон\w*|суд\w*|иск\w*|прокуратур\w*|роспотребнадзор\w*|банк росси\w*|"
                        r"цб\b|статья|ст\.\s*\d+)", re.I)
_CONDITIONAL = re.compile(r"\b(если|при условии|за исключением|кроме|только|не менее|не более|не позднее|"
                          r"до|от)\b", re.I)


@dataclass
class Claim:
    id: str
    index: int
    text: str
    substantive: bool
    mentions: list[Mention] = field(default_factory=list)
    topics: set[str] = field(default_factory=set)
    terms: list[str] = field(default_factory=list)
    commitment: bool = False
    absolute: bool = False
    legal_reference: bool = False

    @property
    def financial(self) -> bool:
        return bool(self.mentions) or bool(self.topics & FINANCIAL_TOPICS)

    @property
    def verifiable_mentions(self) -> list[Mention]:
        """Numbers that are claims themselves. A duration stated next to a
        rate/fee ("на 6 месяцев — 14%") is a *condition* of that rate."""
        return [m for m in self.mentions if not is_condition(m, self.mentions)]

    @property
    def conditions(self) -> list[Mention]:
        vm = set(id(m) for m in self.verifiable_mentions)
        return [m for m in self.mentions if id(m) not in vm]

    def flags(self) -> list[str]:
        f = []
        if self.commitment:
            f.append("commitment")
        if self.absolute:
            f.append("absolute_wording")
        if self.legal_reference:
            f.append("legal_reference")
        return f


def is_substantive(sentence: str, mentions: list[Mention]) -> bool:
    if mentions:
        return True
    if sentence.rstrip().endswith("?"):
        return False
    if _COURTESY.search(sentence.strip()):
        return False
    return len(set(content_terms(sentence))) >= 3


def extract_claims(answer: str) -> list[Claim]:
    claims: list[Claim] = []
    for i, sentence in enumerate(split_sentences(answer)):
        mentions = extract_mentions(sentence)
        claims.append(Claim(
            id=f"c{i + 1}", index=i, text=sentence,
            substantive=is_substantive(sentence, mentions),
            mentions=mentions, topics=topics_of(sentence), terms=content_terms(sentence),
            commitment=bool(_COMMITMENT.search(sentence)),
            absolute=bool(_ABSOLUTE.search(sentence)),
            legal_reference=bool(_LEGAL_REF.search(sentence)),
        ))
    return claims


_LEGAL_Q = re.compile(
    r"законн\w*|незаконн\w*|одностороннем|\bсуд\w*|оспор\w*|\bиск\w*|претензи\w*|прав\w* потребител\w*|"
    r"по закону|имеет ли (банк )?право|вправе ли|обязан ли|ответственност\w*",
    re.I,
)


def is_legal_interpretation_question(question: str) -> bool:
    return bool(_LEGAL_Q.search(question))


def has_conditions(text: str) -> int:
    return len(_CONDITIONAL.findall(text))
