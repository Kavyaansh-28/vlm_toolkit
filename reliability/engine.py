"""Claim and candidate reliability with unavailable-probability redistribution."""
from __future__ import annotations

from collections import Counter
from core.schemas import Candidate


def _key(c):
    return (c.type, c.subject, c.attribute, str(c.value), c.object, c.instance_id)


def agreement(candidates: list[Candidate]) -> None:
    total = max(1, len(candidates))
    counts = Counter(_key(c) for candidate in candidates for c in candidate.claims)
    for candidate in candidates:
        candidate.agreement = round(sum(counts[_key(c)] / total for c in candidate.claims) / len(candidate.claims), 2) if candidate.claims else 0.0


def score(candidate: Candidate, weights: dict[str, float], high=.80, low=.40) -> None:
    evidence_by_id = {e.claim_id: e for e in candidate.evidence}
    candidate.claim_reliability = {}
    for claim in candidate.claims:
        evidence = evidence_by_id.get(claim.id)
        # Status and evidence quality matter separately: an unavailable verifier
        # cannot contribute a neutral-looking fabricated confidence.
        if evidence is None or evidence.status == "AMBIGUOUS":
            value = .5
        elif evidence.status == "SUPPORTED":
            value = evidence.score
        elif evidence.status in {"CONTRADICTED", "UNSUPPORTED"}:
            value = evidence.score
        else:  # legacy status compatibility
            value = evidence.score
        candidate.claim_reliability[claim.id] = round(value, 3)

    known = [(e.score, e.evidence_quality if e.evidence_quality is not None else 1.0)
             for e in candidate.evidence if e.status != "AMBIGUOUS"]
    verification = (sum(score * quality for score, quality in known) / sum(q for _, q in known)
                    if known and sum(q for _, q in known) else .5)
    # Provider token probabilities are genuinely absent unless an adapter supplies
    # them. Redistribute their configured mass to visual verification.
    wp = weights.get("probability", 0.0) if candidate.probability_available and candidate.probability is not None else 0.0
    wv = max(0.0, weights.get("verification", 0.0)) + max(0.0, weights.get("probability", 0.0) - wp)
    wa = max(0.0, weights.get("agreement", 0.0))
    denom = wv + wp + wa
    if denom <= 0:
        wv, wa, denom = 1.0, 0.0, 1.0
    visual_score = (verification * wv + (candidate.probability or 0.0) * wp + candidate.agreement * wa) / denom
    candidate.reliability = round(max(0.0, min(1.0, visual_score)), 2)

    statuses = {e.status for e in candidate.evidence}
    actionable = any(e.status == "CONTRADICTED" and e.evidence_quality and e.evidence_quality >= .8 and
                     e.diagnosis in {"OBJECT_HALLUCINATION", "ATTRIBUTE_BINDING_ERROR", "ATTRIBUTE_ERROR", "QUANTITY_ERROR"}
                     for e in candidate.evidence)
    if actionable:
        candidate.decision = "CORRECT"
    elif "AMBIGUOUS" in statuses or "UNSUPPORTED" in statuses:
        candidate.decision = "ABSTAIN"
    elif candidate.reliability >= high and "CONTRADICTED" not in statuses:
        candidate.decision = "ACCEPT"
    elif candidate.reliability <= low and not candidate.evidence:
        candidate.decision = "ABSTAIN"
    else:
        candidate.decision = "ABSTAIN"
