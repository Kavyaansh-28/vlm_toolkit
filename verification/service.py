"""Paper-conformant claim verification service.

Existence is verified by open-vocabulary grounding. Attribute bindings are
verified on those exact grounded crops. No language-model judgement is used as
a substitute for either visual verifier.

Every evidence ``score`` is the claim's verification value v_i in [0, 1]
(high = supported): s_obj, s_attr, s_obj for a matching count (else 0), and
min(s_subj, s_obj) for a relation whose geometry holds (else 0).
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from core.config import ROOT, raw_config
from core.schemas import Claim, Evidence
from verification.attribute_verifier import AttributeVerifier, CLIPRegionProbe
from verification.cache import VerificationCache
from verification.grounding import CachedGrounder, GroundingDINO
from verification.object_verifier import ObjectVerifier

_STATE: dict = {"verifiers": None, "cache_name": "verification", "cache_only": False, "device": None}


def configure(cache_name: str | None = None, cache_only: bool | None = None, device: str | None = None) -> None:
    """Select the cache file / offline mode; rebuilds the verifiers on next use."""
    if cache_name is not None: _STATE["cache_name"] = cache_name
    if cache_only is not None: _STATE["cache_only"] = cache_only
    if device is not None: _STATE["device"] = device
    _STATE["verifiers"] = None


def _verifiers() -> tuple[ObjectVerifier, AttributeVerifier, float]:
    if _STATE["verifiers"] is None:
        options = raw_config().get("verification", {})
        local_only = bool(options.get("local_files_only", False))
        device = _STATE["device"] or str(options.get("device", "auto"))
        threshold = float(options.get("grounding_threshold", .30))
        cache_dir = Path(options.get("cache_dir", "results/cache"))
        cache_dir = cache_dir if cache_dir.is_absolute() else ROOT / cache_dir
        cache = VerificationCache(cache_dir / f"{_STATE['cache_name']}.jsonl", _STATE["cache_only"])
        grounder = CachedGrounder(GroundingDINO(str(options.get("grounding_model", "IDEA-Research/grounding-dino-tiny")),
                                                float(options.get("detect_floor", .10)), local_only, device), cache)
        probe = CLIPRegionProbe(str(options.get("attribute_model", "openai/clip-vit-base-patch32")), local_only, device)
        _STATE["verifiers"] = (ObjectVerifier(grounder, threshold),
                               AttributeVerifier(probe, float(options.get("attribute_threshold", .50)), cache), threshold)
    return _STATE["verifiers"]


def _grounding_parts(evidence: Evidence) -> tuple[list[list[float]], list[float]]:
    item = evidence.signals.get("open_vocabulary_grounding", {})
    return list(item.get("boxes", evidence.boxes) or []), list(item.get("box_scores", []) or [])


def _iou(a: list[float], b: list[float]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def count_instances(boxes: list[list[float]], scores: list[float], threshold: float, iou: float = .5) -> list[list[float]]:
    """Greedy NMS over boxes at/above the support threshold."""
    kept: list[list[float]] = []
    for box, _ in sorted(((b, s) for b, s in zip(boxes, scores) if s >= threshold), key=lambda row: -row[1]):
        if all(_iou(box, other) <= iou for other in kept):
            kept.append(box)
    return kept


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


def verify(image_path: str, claims: list[Claim], attribute: bool = True) -> list[Evidence]:
    """Verify claims from detector/crop evidence.

    ``attribute=False`` is the object-only (Woodpecker-style) ablation:
    attribute claims receive no evidence and are left untouched by policy.
    """
    if not claims: return []
    object_verifier, attribute_verifier, threshold = _verifiers()
    object_evidence: dict[str, Evidence] = {}
    subjects = {claim.subject for claim in claims}
    subjects.update(claim.object for claim in claims if claim.object)
    for subject in sorted(x for x in subjects if x):
        object_evidence[subject] = object_verifier.verify_object(subject, image_path)

    output: list[Evidence] = []
    for claim in claims:
        object_ev = object_evidence[claim.subject]
        if claim.type == "object":
            output.append(replace(object_ev, claim_id=claim.id)); continue
        all_boxes, all_scores = _grounding_parts(object_ev)
        if claim.type == "attribute":
            if not attribute: continue
            if object_ev.evidence_quality == 0:
                output.append(Evidence(claim.id, "AMBIGUOUS", .5, object_ev.source, explanation=object_ev.explanation, evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM")); continue
            if object_ev.status != "SUPPORTED":  # a binding cannot hold on an object that is not there
                output.append(Evidence(claim.id, "UNSUPPORTED", 0.0, object_ev.source, evidence_quality=1.0, diagnosis="UNSUPPORTED_CLAIM",
                                       binding_status="AMBIGUOUS", explanation=f"'{claim.subject}' was not localized, so its {claim.attribute} cannot be verified."))
                continue
            output.append(attribute_verifier.verify(image_path, all_boxes, all_scores, claim.attribute or "", str(claim.value), claim.id, claim.subject)); continue
        if claim.type == "quantity":
            if object_ev.evidence_quality == 0:
                output.append(Evidence(claim.id, "AMBIGUOUS", .5, object_ev.source, explanation=object_ev.explanation, evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM"))
            else:
                kept = count_instances(all_boxes, all_scores, threshold)
                observed, expected = len(kept), int(claim.value or 0)
                supported = observed == expected and observed > 0
                output.append(Evidence(claim.id, "SUPPORTED" if supported else "CONTRADICTED", object_ev.score if supported else 0.0, object_ev.source,
                                       boxes=kept, verified_value=observed, evidence_quality=1.0, diagnosis=None if supported else "QUANTITY_ERROR",
                                       explanation=f"Grounding DINO localized {observed} instance(s) after NMS (threshold {threshold:.2f}); claim states {expected}."))
            continue
        if claim.type == "relation":
            target_ev = object_evidence.get(claim.object or "")
            boxes, target_boxes = object_ev.boxes, target_ev.boxes if target_ev else []
            if object_ev.evidence_quality == 0 or not target_ev or target_ev.evidence_quality == 0 or not boxes or not target_boxes:
                output.append(Evidence(claim.id, "AMBIGUOUS", .5, ["grounding-dino"], boxes=boxes + target_boxes, explanation="Both objects must be localized before relation geometry can be checked.", evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM"))
            else:
                supported = any(_relation_status(str(claim.value), a, b) for a in boxes for b in target_boxes)
                strength = min(object_ev.score, target_ev.score)
                output.append(Evidence(claim.id, "SUPPORTED" if supported else "CONTRADICTED", strength if supported else 0.0, ["grounding-dino-geometry"], boxes=boxes + target_boxes, explanation=f"Detected-box geometry {'supports' if supported else 'contradicts'} {claim.value}.", evidence_quality=1.0, diagnosis=None if supported else "RELATION_ERROR"))
            continue
        output.append(Evidence(claim.id, "AMBIGUOUS", .5, ["verification"], explanation="Unsupported claim type.", evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM"))
    return output
