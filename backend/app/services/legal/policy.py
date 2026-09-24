"""Risk calibration and proportional handling policy (section 7.3)."""
from __future__ import annotations

from .claims import Claim
from .verifier import CONFIRMED, CONTRADICTED, NEEDS_REVIEW, OUTDATED, UNVERIFIED

LOW, MEDIUM, HIGH, CRITICAL = "LOW", "MEDIUM", "HIGH", "CRITICAL"
RISK_ORDER = [LOW, MEDIUM, HIGH, CRITICAL]


def max_risk(risks: list[str]) -> str:
    return max(risks, key=RISK_ORDER.index) if risks else LOW


def assess_risk(claim: Claim, status: str) -> str:
    if status == CONFIRMED:
        return LOW
    if status == CONTRADICTED:
        if claim.commitment:
            return CRITICAL
        return HIGH if claim.financial else MEDIUM
    if status == UNVERIFIED:
        if claim.commitment:
            return CRITICAL
        if claim.verifiable_mentions or claim.legal_reference:
            return HIGH
        return MEDIUM if claim.financial else LOW
    if status == OUTDATED:
        return HIGH if (claim.verifiable_mentions and claim.financial) else MEDIUM
    return HIGH


def escalate_for_review(claim: Claim, status: str, legal_question: bool) -> bool:
    """Should a non-confirmed claim be routed to expert review?"""
    if status == CONFIRMED:
        return False
    if legal_question:
        return True
    return claim.legal_reference and status in (UNVERIFIED, OUTDATED)


# Customer-facing cautions. They contain no facts and no promises.
CAUTION_UNVERIFIED = ("Часть условий я не могу подтвердить по действующим документам банка — "
                      "уточните их, пожалуйста, у специалиста банка.")
CAUTION_ACTUALITY = ("Эти сведения основаны на источнике, актуальность которого не подтверждена, — "
                     "уточните действующие условия перед принятием решения.")
CAUTION_LEGAL = ("Ваш вопрос требует юридической оценки конкретной ситуации — "
                 "окончательный ответ даст специалист банка после проверки.")
CAUTION_MEDIUM = "Точные условия для вашего случая уточните в действующих документах по продукту."

__all__ = ["LOW", "MEDIUM", "HIGH", "CRITICAL", "RISK_ORDER", "max_risk", "assess_risk",
           "escalate_for_review", "CONFIRMED", "CONTRADICTED", "UNVERIFIED", "OUTDATED", "NEEDS_REVIEW",
           "CAUTION_UNVERIFIED", "CAUTION_ACTUALITY", "CAUTION_LEGAL", "CAUTION_MEDIUM"]
