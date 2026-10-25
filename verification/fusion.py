"""Evidence fusion with explicit unavailable signals and contradiction handling."""
from __future__ import annotations

from typing import Any


def fuse(claim_id: str, signals: dict[str, Any], explanation: str = "") -> dict[str, Any]:
    """Fuse named signal records without treating missing values as negatives.

    A signal is either a numeric score or ``{"score": ..., "available": bool}``.
    The returned score is the mean of available signals; evidence quality is the
    fraction of configured signals that are actually available.
    """
    normalized: dict[str, dict[str, Any]] = {}
    for name, raw in signals.items():
        item = raw if isinstance(raw, dict) else {"score": raw, "available": raw is not None}
        available = bool(item.get("available", item.get("score") is not None)) and item.get("score") is not None and item.get("contributes_to_claim", True)
        score = float(item["score"]) if available else None
        if score is not None:
            score = max(0.0, min(1.0, score))
        normalized[name] = {**item, "available": available, "score": score}
    active = [item["score"] for item in normalized.values() if item["available"]]
    eligible = sum(1 for raw in signals.values() if not isinstance(raw, dict) or raw.get("contributes_to_claim", True))
    quality = len(active) / eligible if eligible else 0.0
    score = sum(active) / len(active) if active else 0.5
    positive = any(x >= .75 for x in active)
    negative = any(x <= .25 for x in active)
    if positive and negative:
        status = "AMBIGUOUS"
    elif positive:
        status = "SUPPORTED"
    elif negative:
        status = "CONTRADICTED"
    else:
        status = "UNSUPPORTED"
    return {"claim_id": claim_id, "status": status, "score": round(score, 3),
            "evidence_quality": round(quality, 3), "signals": normalized,
            "explanation": explanation}
