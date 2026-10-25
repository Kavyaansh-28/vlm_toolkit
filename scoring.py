"""Transparent MVP scoring policy."""
from __future__ import annotations

HIGH_THRESHOLD = 0.80
LOW_THRESHOLD = 0.40


def score_claims(rows: list[dict]) -> dict:
    scores = [float(row["score"]) for row in rows]
    value = sum(scores) / len(scores) if scores else 0.5
    decision = "ACCEPT" if value >= HIGH_THRESHOLD else "CORRECT" if value <= LOW_THRESHOLD else "FLAG"
    return {"reliability_score": round(value, 2), "decision": decision}
