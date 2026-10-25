"""Object-existence verification: s_obj(o) = max_{b in B_o} d_b."""
from __future__ import annotations

from core.schemas import Evidence
from verification.grounding import Grounder, GroundingDINO


class ObjectVerifier:
    def __init__(self, grounder: Grounder | None = None, threshold: float = .30):
        self.grounder, self.threshold = grounder or GroundingDINO(threshold=threshold), threshold

    def verify_object(self, object_name: str, image_path: str, claim_id: str = "") -> Evidence:
        result = self.grounder.detect(image_path, object_name)
        if not result.available:
            return Evidence(claim_id, "AMBIGUOUS", .5, [result.backend], explanation=result.reason,
                            evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM",
                            signals={"open_vocabulary_grounding": {"available": False, "score": None,
                                     "method": "Grounding DINO", "reason": result.reason}})
        score = max(result.scores, default=0.0)
        if score >= self.threshold:
            status, explanation = "SUPPORTED", f"Grounding DINO localized '{object_name}' with max confidence {score:.3f}."
        else:
            status, explanation = "UNSUPPORTED", f"No '{object_name}' grounding met threshold {self.threshold:.2f}; max confidence {score:.3f}."
        return Evidence(claim_id, status, round(score, 3), [result.backend], confidence=round(score, 3), boxes=result.boxes,
                        explanation=explanation, evidence_quality=1.0,
                        diagnosis=None if status == "SUPPORTED" else "UNSUPPORTED_CLAIM",
                        signals={"open_vocabulary_grounding": {"available": True, "score": round(score, 3),
                                  "boxes": result.boxes, "box_scores": result.scores,
                                  "equation": "s_obj(o)=max_{b in B_o} d_b", "method": "Grounding DINO"}})

