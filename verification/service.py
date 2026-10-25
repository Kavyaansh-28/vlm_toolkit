"""Paper-conformant claim verification service.

Existence is verified by open-vocabulary grounding. Attribute bindings are
verified on those exact grounded crops. No language-model judgement is used as
a substitute for either visual verifier.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import yaml

from core.schemas import Claim, Evidence
from verification.attribute_verifier import AttributeVerifier
from verification.object_verifier import ObjectVerifier
from verification.grounding import GroundingDINO
from verification.attribute_verifier import CLIPRegionProbe


@lru_cache(maxsize=1)
def _verifiers() -> tuple[ObjectVerifier, AttributeVerifier]:
    path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    config = yaml.safe_load(path.read_text()) if path.exists() else {}
    options = config.get("verification", {})
    local_only = bool(options.get("local_files_only", False))
    grounding_threshold = float(options.get("grounding_threshold", .30))
    attribute_threshold = float(options.get("attribute_threshold", .50))
    grounder = GroundingDINO(str(options.get("grounding_model", "IDEA-Research/grounding-dino-tiny")), grounding_threshold, local_only)
    probe = CLIPRegionProbe(str(options.get("attribute_model", "openai/clip-vit-base-patch32")), local_only)
    return ObjectVerifier(grounder, grounding_threshold), AttributeVerifier(probe, attribute_threshold)


def _grounding_parts(evidence: Evidence) -> tuple[list[list[float]], list[float]]:
    item = evidence.signals.get("open_vocabulary_grounding", {})
    return list(item.get("boxes", evidence.boxes) or []), list(item.get("box_scores", []) or [])


def _relation_status(relation: str, subject_box: list[float], object_box: list[float]) -> bool:
    sx1, sy1, sx2, sy2 = subject_box; ox1, oy1, ox2, oy2 = object_box
    scx, scy, ocx, ocy = (sx1+sx2)/2, (sy1+sy2)/2, (ox1+ox2)/2, (oy1+oy2)/2
    if relation == "left_of": return scx < ocx
    if relation == "right_of": return scx > ocx
    if relation == "above": return scy < ocy
    if relation == "below": return scy > ocy
    if relation in {"next_to", "near"}:
        return abs(scx-ocx) + abs(scy-ocy) < max((sx2-sx1)+(sy2-sy1), (ox2-ox1)+(oy2-oy1)) * 2
    return False


def verify(image_path: str, claims: list[Claim], provider: str = "openai") -> list[Evidence]:
    """Verify claims from detector/crop evidence; ``provider`` is legacy-only.

    The optional provider argument is preserved for old callers but does not
    alter visual methodology or invoke an LLM verifier.
    """
    if not claims: return []
    object_verifier, attribute_verifier = _verifiers()
    object_evidence: dict[str, Evidence] = {}
    subjects = {claim.subject for claim in claims if claim.type in {"object", "attribute", "quantity", "relation"}}
    subjects.update(claim.object for claim in claims if claim.object)
    for subject in sorted(x for x in subjects if x):
        object_evidence[subject] = object_verifier.verify_object(subject, image_path)

    output: list[Evidence] = []
    for claim in claims:
        object_ev = object_evidence[claim.subject]
        if claim.type == "object":
            object_ev.claim_id = claim.id
            output.append(object_ev); continue
        boxes, scores = _grounding_parts(object_ev)
        if claim.type == "attribute":
            output.append(attribute_verifier.verify(image_path, boxes, scores, claim.attribute or "", str(claim.value), claim.id)); continue
        if claim.type == "quantity":
            if object_ev.evidence_quality == 0:
                output.append(Evidence(claim.id, "AMBIGUOUS", .5, object_ev.source, boxes=boxes, explanation=object_ev.explanation, evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM"))
            else:
                observed = len(boxes); expected = int(claim.value or 0); supported = observed == expected and observed > 0
                output.append(Evidence(claim.id, "SUPPORTED" if supported else "CONTRADICTED", object_ev.score if supported else 1-object_ev.score, object_ev.source, boxes=boxes, verified_value=observed, explanation=f"Grounding DINO localized {observed} instance(s); claim states {expected}.", evidence_quality=1.0, diagnosis=None if supported else "QUANTITY_ERROR"))
            continue
        if claim.type == "relation":
            target_ev = object_evidence.get(claim.object or "")
            target_boxes, _ = _grounding_parts(target_ev) if target_ev else ([], [])
            if object_ev.evidence_quality == 0 or not target_ev or target_ev.evidence_quality == 0 or not boxes or not target_boxes:
                output.append(Evidence(claim.id, "AMBIGUOUS", .5, ["grounding-dino"], boxes=boxes + target_boxes, explanation="Both objects must be localized before relation geometry can be checked.", evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM"))
            else:
                supported = any(_relation_status(str(claim.value), a, b) for a in boxes for b in target_boxes)
                strength = min(object_ev.score, target_ev.score)
                output.append(Evidence(claim.id, "SUPPORTED" if supported else "CONTRADICTED", strength if supported else 1-strength, ["grounding-dino-geometry"], boxes=boxes + target_boxes, explanation=f"Detected-box geometry {'supports' if supported else 'contradicts'} {claim.value}.", evidence_quality=1.0, diagnosis=None if supported else "RELATION_ERROR"))
            continue
        output.append(Evidence(claim.id, "AMBIGUOUS", .5, ["verification"], explanation="Unsupported claim type.", evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM"))
    return output
