"""Candidate reliability, paper Eq. 3: R_j = l1*mean_i(v_i) + l2*p_j + l3*A_j.

Terms that are genuinely unavailable (no token probabilities from an API model,
no agreement when n == 1, no usable verifier) are never fabricated; their
weight is redistributed to the remaining terms and the record says so.
"""
from __future__ import annotations

from core.config import PipelineConfig
from core.schemas import Candidate


def _key(c):
    return (c.type, c.subject, c.attribute, str(c.value), c.object, c.instance_id)


def agreement(candidates: list[Candidate]) -> None:
    """A_j = fraction of y_j's claims also asserted by at least one of the other n-1 candidates."""
    keys = [{_key(c) for c in candidate.claims} for candidate in candidates]
    for index, candidate in enumerate(candidates):
        others = [k for j, k in enumerate(keys) if j != index]
        candidate.agreement_available = bool(others and keys[index])
        candidate.agreement = (round(sum(any(k in other for other in others) for k in keys[index]) / len(keys[index]), 3)
                               if candidate.agreement_available else 0.0)


def verification_values(candidate: Candidate) -> dict[str, float]:
    """v_i per claim whose verifier actually ran (evidence_quality > 0)."""
    claim_ids = {c.id for c in candidate.claims}
    return {e.claim_id: max(0.0, min(1.0, float(e.score))) for e in candidate.evidence
            if e.claim_id in claim_ids and e.evidence_quality and e.status != "AMBIGUOUS"}


def score(candidate: Candidate, cfg: PipelineConfig | dict) -> None:
    weights = cfg.weights if isinstance(cfg, PipelineConfig) else cfg
    values = verification_values(candidate)
    candidate.claim_values = {k: round(v, 3) for k, v in values.items()}
    candidate.claim_reliability = dict(candidate.claim_values)
    terms = {
        "verification": (sum(values.values()) / len(values)) if values else None,
        "probability": candidate.probability if candidate.probability_available and candidate.probability is not None else None,
        "agreement": candidate.agreement if candidate.agreement_available else None,
    }
    active = {name: max(0.0, float(weights.get(name, 0.0))) for name, value in terms.items() if value is not None}
    total = sum(active.values())
    if not active or total <= 0:
        candidate.reliability = 0.0
        return
    candidate.reliability = round(max(0.0, min(1.0, sum(terms[name] * w for name, w in active.items()) / total)), 3)
