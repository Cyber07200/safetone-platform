"""Legal Assurance Engine: claims -> sources -> verification -> correction."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.knowledge.facts import Mention
from .claims import Claim, extract_claims, is_legal_interpretation_question
from .policy import (CAUTION_ACTUALITY, CAUTION_LEGAL, CAUTION_MEDIUM, CAUTION_UNVERIFIED, CONFIRMED,
                     CONTRADICTED, CRITICAL, HIGH, LOW, MEDIUM, NEEDS_REVIEW, OUTDATED, RISK_ORDER, UNVERIFIED,
                     assess_risk, escalate_for_review, max_risk)
from .verifier import Verdict, verify_claim


@dataclass
class ClaimOutcome:
    claim: Claim
    verdict: Verdict
    status: str
    risk: str
    action: str  # keep | corrected | replaced_with_source | removed | kept_with_caution
    new_text: str | None
    corrected_from_source: bool = False
    review: bool = False
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        c = self.claim
        return {
            "id": c.id,
            "text": c.text,
            "substantive": c.substantive,
            "status": self.status,
            "evidence_status": self.verdict.status,
            "risk": self.risk,
            "explanation": self.verdict.explanation,
            "notes": [n for n in self.verdict.notes if not n.startswith("__")],
            "flags": c.flags(),
            "topics": sorted(c.topics),
            "values": [m.to_dict() for m in c.verifiable_mentions],
            "conditions": [m.to_dict() for m in c.conditions],
            "evidence": [e.to_dict() for e in self.verdict.evidence],
            "action": self.action,
            "correction": self.new_text if self.action in ("corrected", "replaced_with_source") else None,
            "requires_review": self.review,
            **self.extra,
        }


@dataclass
class LegalOutcome:
    claims: list[ClaimOutcome]
    corrected_text: str
    changes: list[dict]
    missing_data: list[str]
    cautions: list[str]
    legal_question: bool
    review_reasons: list[str]
    sources: list[dict]

    @property
    def max_risk(self) -> str:
        return max_risk([c.risk for c in self.claims if c.claim.substantive])

    @property
    def needs_review(self) -> bool:
        return bool(self.review_reasons)


def _apply_replacements(text: str, reps: list[tuple[Mention, Mention]]) -> str:
    out = text
    for cm, sm in sorted(reps, key=lambda r: -r[0].start):
        out = out[:cm.start] + sm.raw + out[cm.end:]
    return out


def _rebuild(original: str, claims: list[Claim], replacement: dict[str, str | None]) -> str:
    """Re-assemble text preserving original separators (line breaks, bullets)."""
    parts, pos = [], 0
    for c in claims:
        idx = original.find(c.text, pos)
        if idx < 0:  # should not happen; fall back to plain join
            parts.append(" ")
            idx = pos
            seg_end = pos
        else:
            seg_end = idx + len(c.text)
        sep = original[pos:idx]
        new = replacement.get(c.id, c.text)
        if new is None:
            # drop sentence together with its leading bullet marker if the line becomes empty
            parts.append(sep if "\n" in sep and not sep.strip(" \n-•–") else sep.rstrip(" -•–"))
        else:
            parts.append(sep + new)
        pos = seg_end
    parts.append(original[pos:])
    text = "".join(parts)
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = []
    for ln in lines:
        if ln.strip() in ("-", "•", "–"):
            continue
        cleaned.append(ln)
    text = "\n".join(cleaned)
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return re.sub(r"[ ]{2,}", " ", text).strip()


@dataclass
class Analyzed:
    claim: Claim
    verdict: Verdict
    hits: list


def analyze(db: Session, *, bank_id: str, product_id: str | None, question: str, answer: str) -> list[Analyzed]:
    """Phase 1: claim extraction + retrieval + deterministic evidence verification."""
    out = []
    for c in extract_claims(answer):
        if not c.substantive:
            out.append(Analyzed(c, Verdict(CONFIRMED, "Служебная фраза без проверяемых фактов."), []))
            continue
        verdict, hits = verify_claim(db, bank_id=bank_id, product_id=product_id, question=question, claim=c)
        out.append(Analyzed(c, verdict, hits))
    return out


_SEVERITY = [CONFIRMED, OUTDATED, UNVERIFIED, NEEDS_REVIEW, CONTRADICTED]


def merge_llm(analyzed: list[Analyzed], judgements: dict[str, dict]) -> None:
    """Combine deterministic verdicts with validated LLM judgements.

    The deterministic evidence engine stays authoritative for concrete
    values; the model can confirm a statement only with a verified quote
    from a current source, and any disagreement is escalated to review.
    """
    for a in analyzed:
        j = judgements.get(a.claim.id)
        if not a.claim.substantive or not j:
            continue
        a.verdict.notes.append(f"LLM-верификация: {j['status']} — {j.get('explanation', '')[:300]}"
                               + ("" if j.get("valid") else " (ответ модели отклонён: цитата не подтверждена)"))
        if not j.get("valid"):
            continue
        det, llm = a.verdict.status, j["status"]
        if det == CONFIRMED and llm in (CONTRADICTED, NEEDS_REVIEW):
            a.verdict.status = NEEDS_REVIEW
            a.verdict.explanation += " Модель-верификатор не согласна с автоматической проверкой — нужна экспертиза."
        elif det == UNVERIFIED and llm == CONFIRMED and j.get("current"):
            a.verdict.status = CONFIRMED
            a.verdict.explanation = f"Подтверждено моделью-верификатором с проверенной цитатой: «{j['quote'][:200]}»."
            a.verdict.evidence = j.get("evidence", []) or a.verdict.evidence
        elif det == UNVERIFIED and llm in (CONTRADICTED, NEEDS_REVIEW):
            a.verdict.status = NEEDS_REVIEW
            a.verdict.explanation += " Модель-верификатор указала на противоречие — требуется экспертная проверка."


def finalize(question: str, answer: str, analyzed: list[Analyzed]) -> LegalOutcome:
    """Phase 2: risk policy, proportional correction and text assembly."""
    legal_q = is_legal_interpretation_question(question)
    claims = [a.claim for a in analyzed]
    outcomes: list[ClaimOutcome] = []
    cautions: list[str] = []
    missing: list[str] = []
    review: list[str] = []
    changes: list[dict] = []
    replacement: dict[str, str | None] = {}
    sources: dict[str, dict] = {}

    for a in analyzed:
        c, verdict = a.claim, a.verdict
        if not c.substantive:
            outcomes.append(ClaimOutcome(c, verdict, CONFIRMED, LOW, "keep", None, extra={"skipped": True}))
            continue
        for e in verdict.evidence:
            d = e.to_dict()
            key = d["chunk_id"]
            if key not in sources:
                sources[key] = {k: d[k] for k in ("chunk_id", "document_id", "title", "doc_type", "version",
                                                  "section", "page", "quote", "actuality", "document_date",
                                                  "effective_from", "effective_to", "source_url", "is_demo")}
                sources[key]["used_for"] = []
            sources[key]["used_for"].append({"claim_id": c.id, "relation": d["relation"]})

        ev_status = verdict.status
        forced_review = ev_status == NEEDS_REVIEW
        base = UNVERIFIED if forced_review else ev_status
        risk = assess_risk(c, base)
        is_review = forced_review or escalate_for_review(c, base, legal_q)
        status = NEEDS_REVIEW if is_review else ev_status
        if is_review:
            risk = max_risk([risk, HIGH])

        action, new_text, from_source = "keep", None, False
        if base == CONTRADICTED:
            if verdict.replacements:
                new_text = _apply_replacements(c.text, verdict.replacements)
                action, from_source = "corrected", True
            elif verdict.replace_sentence_with is not None:
                new_text = verdict.replace_sentence_with.clean_text
                action, from_source = "replaced_with_source", True
            else:
                action = "removed"
        elif base == UNVERIFIED:
            if risk in (HIGH, CRITICAL):
                action = "removed"
                missing.append(f"Не найден действующий источник, подтверждающий: «{c.text}»")
                cautions.append(CAUTION_LEGAL if is_review and legal_q else CAUTION_UNVERIFIED)
            elif risk == MEDIUM:
                action = "kept_with_caution"
                cautions.append(CAUTION_LEGAL if legal_q else CAUTION_MEDIUM)
        elif base == OUTDATED:
            action = "kept_with_caution"
            cautions.append(CAUTION_ACTUALITY)
            missing.append(f"Нужна действующая редакция источника для: «{c.text}»")
        if is_review and legal_q and CAUTION_LEGAL not in cautions:
            cautions.append(CAUTION_LEGAL)

        if action in ("corrected", "replaced_with_source"):
            replacement[c.id] = new_text
        elif action == "removed":
            replacement[c.id] = None
        if action != "keep":
            changes.append({
                "claim_id": c.id, "action": action, "before": c.text,
                "after": replacement.get(c.id, c.text) if action != "kept_with_caution" else c.text,
                "reason": verdict.explanation, "risk": risk,
                "basis": [{"title": e.sentence.hit.doc.title, "section": e.sentence.hit.section,
                           "version": e.sentence.hit.doc.version, "actuality": e.sentence.hit.doc.actuality,
                           "relation": e.relation}
                          for e in verdict.evidence if e.relation in ("contradicts", "supports")][:2],
            })

        if status == NEEDS_REVIEW:
            why = ("юридический вопрос" if legal_q else
                   "разногласие проверок" if forced_review else "ссылка на нормы без подтверждения")
            review.append(f"{c.id}: требуется экспертная проверка ({why})")
        elif risk == CRITICAL:
            review.append(f"{c.id}: критичный риск — даже исправленный ответ должен подтвердить специалист")
        elif risk == HIGH and not from_source:
            review.append(f"{c.id}: существенное утверждение не подтверждено действующим источником")

        outcomes.append(ClaimOutcome(c, verdict, status, risk, action, new_text, from_source, is_review))

    corrected = _rebuild(answer, claims, replacement)
    uniq_cautions = list(dict.fromkeys(cautions))
    for caution in uniq_cautions:
        if caution not in corrected:
            corrected = (corrected + "\n\n" + caution).strip()
    if not corrected.strip():
        corrected = CAUTION_UNVERIFIED
    return LegalOutcome(outcomes, corrected, changes, list(dict.fromkeys(missing)), uniq_cautions, legal_q,
                        review, list(sources.values()))


def run_legal(db: Session, *, bank_id: str, product_id: str | None, question: str, answer: str) -> LegalOutcome:
    """Deterministic legal pass (Demo Mode and fallback)."""
    return finalize(question, answer, analyze(db, bank_id=bank_id, product_id=product_id,
                                              question=question, answer=answer))


__all__ = ["run_legal", "analyze", "finalize", "merge_llm", "Analyzed", "LegalOutcome", "ClaimOutcome",
           "RISK_ORDER"]
