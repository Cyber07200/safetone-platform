"""Evidence-based verification of claims against retrieved sources.

For every claim we look for source sentences about the *same subject*
(topic + qualifier + conditions) and compare the concrete values. The
result is one of CONFIRMED / CONTRADICTED / UNVERIFIED / OUTDATED_SOURCE,
always with the evidence that led to it. Nothing is decided by keyword
presence alone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.knowledge import retrieval
from app.services.knowledge.facts import (Mention, is_condition, special_case_mismatch, extract_mentions, secondary_conflict, topic_similarity,
                                          units_compatible)
from app.services.knowledge.text import content_terms, split_sentences, tokens
from .claims import Claim

CONFIRMED, CONTRADICTED, UNVERIFIED, OUTDATED, NEEDS_REVIEW = (
    "CONFIRMED", "CONTRADICTED", "UNVERIFIED", "OUTDATED_SOURCE", "NEEDS_REVIEW")

_NEG = {"не", "нет", "нельзя", "невозможно", "ни"}
_EXCEPTION = re.compile(r"за исключением|кроме случа|если\b|при условии", re.I)
_GENERIC = {"банк", "клиент", "вы", "ваш", "ваше", "мы", "наш", "эт", "котор",
            # bureaucratic filler stems: they carry no facts and must not lower support
            "цел", "осуществлен", "осуществ", "осуществля", "процедур", "надлежа", "надлеж", "подач",
            "явля", "данн", "соответств", "необходим", "имет", "производ"}
_CLAUSE_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")


@dataclass
class SourceSentence:
    hit: retrieval.Hit
    text: str
    mentions: list[Mention]
    terms: set[str]
    negated: bool

    @property
    def current(self) -> bool:
        return self.hit.doc.actuality == "current"

    @property
    def clean_text(self) -> str:
        return _CLAUSE_PREFIX.sub("", self.text).strip()


@dataclass
class Evidence:
    relation: str  # supports | contradicts | related | matches_outdated
    sentence: SourceSentence
    claim_value: str | None = None
    source_value: str | None = None

    def to_dict(self) -> dict:
        h = self.sentence.hit
        return {
            "relation": self.relation,
            "chunk_id": h.chunk_id,
            "document_id": h.doc.id,
            "title": h.doc.title,
            "doc_type": h.doc.doc_type,
            "version": h.doc.version,
            "section": h.section,
            "page": h.page,
            "quote": self.sentence.clean_text,
            "actuality": h.doc.actuality,
            "document_date": h.doc.document_date,
            "effective_from": h.doc.effective_from,
            "effective_to": h.doc.effective_to,
            "source_url": h.doc.source_url,
            "is_demo": h.doc.is_demo,
            "claim_value": self.claim_value,
            "source_value": self.source_value,
            "retrieval_score": h.score,
        }


@dataclass
class Verdict:
    status: str
    explanation: str
    evidence: list[Evidence] = field(default_factory=list)
    replacements: list[tuple[Mention, Mention]] = field(default_factory=list)  # (claim, source)
    replace_sentence_with: SourceSentence | None = None
    notes: list[str] = field(default_factory=list)


def _negated(text: str) -> bool:
    return any(t in _NEG for t in tokens(text))


def _source_sentences(hits: list[retrieval.Hit]) -> list[SourceSentence]:
    out = []
    for h in hits:
        for s in split_sentences(h.text):
            out.append(SourceSentence(h, s, extract_mentions(s), set(content_terms(s)), _negated(s)))
    return out


def _overlap(claim_terms: set[str], s: SourceSentence) -> float:
    ct = claim_terms - _GENERIC
    if not ct:
        return 0.0
    return len(ct & s.terms) / len(ct)


def _condition_conflict(claim: Claim, s: SourceSentence) -> bool:
    """Claim and source are about different conditions (e.g. deposit term
    24 months vs 6 months) -> the source value does not apply."""
    c_dur = [m for m in claim.conditions if m.unit in ("months", "days")]
    s_dur = [m for m in s.mentions if is_condition(m, s.mentions)]
    if not c_dur or not s_dur:
        return False
    return not any(abs(a.value - b.value) < 1e-9 and a.unit == b.unit for a in c_dur for b in s_dur)


def _condition_free(s: SourceSentence) -> bool:
    return not any(is_condition(m, s.mentions) for m in s.mentions)


def _fmt(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _verify_mention(claim: Claim, cm: Mention, sents: list[SourceSentence],
                    claim_terms: set[str]) -> Verdict:
    cands: list[tuple[float, SourceSentence, Mention]] = []
    conflicting_conditions = False
    for s in sents:
        if _condition_conflict(claim, s):
            conflicting_conditions = conflicting_conditions or any(
                units_compatible(cm, sm) and topic_similarity(cm, sm) > 0 for sm in s.mentions)
            continue
        lex = _overlap(claim_terms, s)
        for sm in s.mentions:
            if not units_compatible(cm, sm) or secondary_conflict(cm, sm) or special_case_mismatch(cm, sm):
                continue
            sim = topic_similarity(cm, sm)
            if sim <= 0:
                continue
            score = 0.6 * sim + 0.4 * lex
            if score >= 0.3:
                cands.append((score, s, sm))
    if conflicting_conditions and any(m.unit in ("months", "days") for m in claim.conditions):
        # the product has condition-specific values (e.g. rate per deposit term) and none matches
        # the claimed condition: sources without a condition cannot be applied to it
        cands = [c for c in cands if not _condition_free(c[1]) or c[2].value == cm.value]
    equal = lambda sm: abs(sm.value - cm.value) < 1e-9  # noqa: E731
    current = [c for c in cands if c[1].current]
    other = [c for c in cands if not c[1].current]

    cur_eq = sorted([c for c in current if equal(c[2])], key=lambda c: -c[0])
    if cur_eq:
        _, s, sm = cur_eq[0]
        return Verdict(CONFIRMED, f"Значение «{cm.raw}» подтверждено действующим источником.",
                       [Evidence("supports", s, cm.raw, sm.raw)])
    if current:
        current.sort(key=lambda c: -c[0])
        best = current[0]
        rival_sents = {id(c[1]) for c in current if best[0] - c[0] < 0.05 and not equal(c[2])}
        rivals = {c[2].value for c in current if best[0] - c[0] < 0.05 and not equal(c[2])}
        if len(rivals) > 1 and len(rival_sents) > 1:
            return Verdict(UNVERIFIED,
                           f"Для «{cm.raw}» найдено несколько разных значений в источниках "
                           f"({', '.join(sorted({c[2].raw for c in current[:4]}))}); однозначно определить "
                           f"применимое условие не удалось.",
                           [Evidence("related", c[1], cm.raw, c[2].raw) for c in current[:3]])
        _, s, sm = best
        v = Verdict(CONTRADICTED,
                    f"В ответе указано «{cm.raw}», а в действующем источнике — «{sm.raw}».",
                    [Evidence("contradicts", s, cm.raw, sm.raw)], replacements=[(cm, sm)])
        old_eq = [c for c in other if equal(c[2])]
        if old_eq:
            o = old_eq[0][1]
            v.evidence.append(Evidence("matches_outdated", o, cm.raw, old_eq[0][2].raw))
            v.notes.append(f"Значение «{cm.raw}» совпадает с документом «{o.hit.doc.title}» "
                           f"(версия {o.hit.doc.version}, статус: {o.hit.doc.actuality}) — он не действует.")
        return v
    if other:
        other.sort(key=lambda c: -c[0])
        eq = [c for c in other if equal(c[2])]
        if eq:
            _, s, sm = eq[0]
            return Verdict(OUTDATED,
                           f"«{cm.raw}» совпадает с источником, актуальность которого не подтверждена "
                           f"(статус: {s.hit.doc.actuality}).",
                           [Evidence("supports", s, cm.raw, sm.raw)])
        _, s, sm = other[0]
        return Verdict(OUTDATED,
                       f"Найден только неактуальный или непроверенный источник со значением «{sm.raw}»; "
                       f"подтвердить «{cm.raw}» по действующим документам нельзя.",
                       [Evidence("related", s, cm.raw, sm.raw)])
    return Verdict(UNVERIFIED, f"В базе знаний не найден источник, подтверждающий «{cm.raw}».")


def _verify_statement(claim: Claim, sents: list[SourceSentence], claim_terms: set[str]) -> Verdict:
    scored = sorted(((_overlap(claim_terms, s), s) for s in sents), key=lambda x: -x[0])
    cur = [(o, s) for o, s in scored if s.current]
    oth = [(o, s) for o, s in scored if not s.current]
    claim_neg = _negated(claim.text)

    def judge(o: float, s: SourceSentence, outdated: bool) -> Verdict:
        if claim_neg != s.negated:
            status = OUTDATED if outdated else CONTRADICTED
            return Verdict(status, "Источник утверждает противоположное."
                           + (" Источник не подтверждён как действующий." if outdated else ""),
                           [Evidence("contradicts", s)], replace_sentence_with=None if outdated else s)
        if claim.absolute and _EXCEPTION.search(s.text):
            status = OUTDATED if outdated else CONTRADICTED
            return Verdict(status, "Утверждение сформулировано как абсолютное, а источник содержит "
                                   "исключения или условия.",
                           [Evidence("contradicts", s)], replace_sentence_with=None if outdated else s)
        if outdated:
            return Verdict(OUTDATED, f"Утверждение совпадает с источником, актуальность которого не подтверждена "
                                     f"(статус: {s.hit.doc.actuality}).", [Evidence("supports", s)])
        return Verdict(CONFIRMED, f"Утверждение подтверждено действующим источником (совпадение {o:.0%}).",
                       [Evidence("supports", s)])

    if cur and cur[0][0] >= 0.6:
        return judge(cur[0][0], cur[0][1], outdated=False)
    if oth and oth[0][0] >= 0.6:
        return judge(oth[0][0], oth[0][1], outdated=True)
    if claim.absolute:
        for o, s in cur[:5]:
            if o >= 0.4 and _EXCEPTION.search(s.text):
                return Verdict(CONTRADICTED, "Утверждение сформулировано как абсолютное, а действующий источник "
                                             "содержит исключения или условия.",
                               [Evidence("contradicts", s)], replace_sentence_with=s)
    best = (cur[:1] + oth[:1])
    best.sort(key=lambda x: -x[0])
    if best and best[0][0] >= 0.35:
        return Verdict(UNVERIFIED, "Найдены только частично связанные положения; прямого подтверждения нет.",
                       [Evidence("related", best[0][1])])
    return Verdict(UNVERIFIED, "В базе знаний не найдено положений, подтверждающих это утверждение.")


def verify_claim(db: Session, *, bank_id: str, product_id: str | None, question: str,
                 claim: Claim, top_k: int = 8) -> tuple[Verdict, list[retrieval.Hit]]:
    query = f"{claim.text} {claim.text} {question}"
    hits = retrieval.search(db, bank_id=bank_id, product_id=product_id, query=query, top_k=top_k)
    sents = _source_sentences(hits)
    claim_terms = set(claim.terms)
    mentions = claim.verifiable_mentions
    if not mentions:
        return _verify_statement(claim, sents, claim_terms), hits

    verdicts = [_verify_mention(claim, m, sents, claim_terms) for m in mentions]
    order = [CONTRADICTED, UNVERIFIED, OUTDATED, CONFIRMED]
    worst = min(verdicts, key=lambda v: order.index(v.status))
    merged = Verdict(worst.status, " ".join(v.explanation for v in verdicts))
    for v in verdicts:
        merged.evidence.extend(v.evidence)
        merged.notes.extend(v.notes)
    contradictions = [v for v in verdicts if v.status == CONTRADICTED]
    if contradictions:
        reps = [r for v in contradictions for r in v.replacements]
        # a zero-fee mismatch cannot be fixed by swapping numbers: use the source wording
        if any(cm.unit == "fee_zero" or sm.unit == "fee_zero" for cm, sm in reps):
            merged.replace_sentence_with = contradictions[0].evidence[0].sentence
        else:
            merged.replacements = reps
    return merged, hits
