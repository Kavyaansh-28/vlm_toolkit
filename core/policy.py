"""Decision policy, paper Sec. IV-E.

Per claim (thresholds lo < hi): accept if v >= hi; correct if v <= lo and the
verifier supplies positive evidence for the fix; otherwise abstain / flag.
Per response: re-rank to argmax_j R_j only when the original top candidate
falls below the reliability threshold and another candidate satisfies it.
"""
from __future__ import annotations

from core.config import PipelineConfig
from core.schemas import Candidate, Claim, Evidence


def claim_action(v: float | None, evidence: Evidence | None, claim: Claim, cfg: PipelineConfig) -> str:
    if evidence is None:
        # Attribute claims are deliberately unverified in the object-only ablation.
        return "ACCEPT" if claim.type == "attribute" and not cfg.attribute_verifier else "ABSTAIN"
    if evidence.status == "AMBIGUOUS" or not evidence.evidence_quality or v is None:
        return "ABSTAIN"  # verifier unavailable: never a silent accept or correction
    lo, hi = cfg.bounds(claim.type)
    if v >= hi:
        return "ACCEPT"
    if v <= lo:
        if claim.type == "object" and v < cfg.grounding_threshold:
            return "CORRECT"  # no detection at all -> delete (no evidence for a substitute)
        if claim.type in {"attribute", "quantity"} and evidence.verified_value not in (None, "", 0):
            return "CORRECT"  # replace with the value observed on the same region
        return "ABSTAIN"      # low score but nothing to substitute (e.g. relations)
    return "ABSTAIN"          # lo < v < hi -> flag for human review


def assign_actions(candidate: Candidate, cfg: PipelineConfig) -> None:
    evidence = {e.claim_id: e for e in candidate.evidence}
    candidate.claim_actions = {
        claim.id: claim_action(candidate.claim_values.get(claim.id), evidence.get(claim.id), claim, cfg)
        for claim in candidate.claims}


def select(candidates: list[Candidate], cfg: PipelineConfig) -> tuple[int, str, str]:
    """Return (index of the chosen candidate, response decision, reason)."""
    original = candidates[0]
    chosen, decision, reason = 0, "", ""
    if cfg.reliability and len(candidates) > 0:
        if original.reliability < cfg.rerank_threshold:
            best = max(range(len(candidates)), key=lambda i: candidates[i].reliability)
            if best != 0 and candidates[best].reliability >= cfg.rerank_threshold:
                chosen, decision = best, "RERANK"
                reason = (f"Top candidate R={original.reliability:.2f} < {cfg.rerank_threshold:.2f}; "
                          f"{candidates[best].id} has R={candidates[best].reliability:.2f}.")
            elif "CORRECT" not in original.claim_actions.values():
                # Low R is expected when errors were found; it only means "no reliable
                # candidate" when nothing could be repaired with evidence either.
                decision = "ABSTAIN"
                reason = f"No candidate reaches R >= {cfg.rerank_threshold:.2f} and no evidence-backed correction exists; escalated for human review."
    if not decision:
        actions = set(candidates[chosen].claim_actions.values())
        if "CORRECT" in actions:
            decision, reason = "CORRECT", "Evidence-backed corrections applied; verified content left untouched."
        elif "ABSTAIN" in actions:
            decision, reason = "ABSTAIN", "Some claims fall between thresholds or lack evidence; flagged as uncertain and left unchanged."
        else:
            decision, reason = "ACCEPT", "All claims meet the accept threshold."
    return chosen, decision, reason
