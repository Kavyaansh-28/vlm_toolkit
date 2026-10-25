"""CHAIR (Rohrbach et al., 2018): object hallucination in captions.

CHAIR_S = fraction of captions with at least one hallucinated object.
CHAIR_I = hallucinated object mentions / all object mentions.
Object recall (paper Sec. V-A) = |mentioned & GT| / |GT|; it exposes over-deletion.
Mentions are found with the CHAIR synonym list (claims.vocab), COCO classes only.
"""
from __future__ import annotations

from claims.vocab import find_objects


def mentioned_objects(text: str) -> set[str]:
    return {cls for cls, _, _ in find_objects(text, include_extra=False)}


def chair(rows: list[dict], text_key: str = "final_text") -> dict:
    if not rows:
        return {"benchmark": "CHAIR", "status": "NOT RUN", "sample_count": 0}
    captions = hallucinated_caps = mentions = hallucinated = gt_total = matched = words = 0
    for row in rows:
        gt, said = set(row.get("gt_objects", [])), mentioned_objects(row.get(text_key) or "")
        bad = said - gt
        captions += 1; hallucinated_caps += bool(bad); mentions += len(said); hallucinated += len(bad)
        gt_total += len(gt); matched += len(said & gt); words += len((row.get(text_key) or "").split())
    return {"benchmark": "CHAIR", "status": "EVALUATED", "sample_count": captions,
            "CHAIR_S": hallucinated_caps / captions, "CHAIR_I": hallucinated / mentions if mentions else 0.0,
            "object_recall": matched / gt_total if gt_total else 0.0, "avg_length": words / captions}
