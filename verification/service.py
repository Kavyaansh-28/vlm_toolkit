"""Batched, image-grounded claim verification through a vision-language model."""
from __future__ import annotations

import json
import re

from core.schemas import Claim, Evidence
from vlm import run_vlm_task

STATUSES = {"SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "AMBIGUOUS"}
ERROR_TYPES = {
    "OBJECT_HALLUCINATION", "ATTRIBUTE_ERROR", "ATTRIBUTE_BINDING_ERROR", "QUANTITY_ERROR",
    "RELATION_ERROR", "UNSUPPORTED_CLAIM", "CONTRADICTED_CLAIM", "AMBIGUOUS_CLAIM",
    "MULTI_CLAIM_CONTRADICTION",
}


def _parse_response(text: str) -> list[dict]:
    """Accept JSON with optional Markdown fences, but never guess missing claims."""
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            payload = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return []
    rows = payload.get("verifications", []) if isinstance(payload, dict) else payload
    return rows if isinstance(rows, list) else []


def _diagnosis(claim: Claim, status: str, proposed: object) -> str | None:
    if isinstance(proposed, str) and proposed.upper() in ERROR_TYPES:
        return proposed.upper()
    if status == "AMBIGUOUS":
        return "AMBIGUOUS_CLAIM"
    if status == "UNSUPPORTED":
        return "UNSUPPORTED_CLAIM"
    if status == "CONTRADICTED":
        if claim.type == "object":
            return "OBJECT_HALLUCINATION"
        if claim.type == "attribute":
            return "ATTRIBUTE_BINDING_ERROR"
        if claim.type == "quantity":
            return "QUANTITY_ERROR"
        if claim.type == "relation":
            return "RELATION_ERROR"
        return "CONTRADICTED_CLAIM"
    return None


def _evidence(claim: Claim, row: dict | None, provider: str, model: str,
              unavailable_reason: str | None = None) -> Evidence:
    if row is None:
        return Evidence(
            claim.id, "AMBIGUOUS", .5, [f"{provider}-vision-verifier-unavailable"],
            explanation=unavailable_reason or "The verifier returned no structured result for this claim.",
            evidence_quality=0.0,
            signals={"vlm_verification": {"available": False, "score": None, "provider": provider,
                                           "model": model, "calibrated": False}},
            diagnosis="AMBIGUOUS_CLAIM", binding_status="AMBIGUOUS" if claim.type == "attribute" else None,
        )

    status = str(row.get("status", "AMBIGUOUS")).upper()
    if status not in STATUSES:
        status = "AMBIGUOUS"
    try:
        confidence = max(0.0, min(1.0, float(row.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    if status == "SUPPORTED":
        score = confidence
    elif status == "CONTRADICTED":
        score = 1.0 - confidence
    else:
        score = .5
    observed = row.get("observed_value")
    if not isinstance(observed, (str, int, float, list, type(None))):
        observed = None
    reason = row.get("reason")
    if not isinstance(reason, str):
        reason = "No verifier explanation was returned."
    diagnosis = _diagnosis(claim, status, row.get("error_type"))
    return Evidence(
        claim.id, status, round(score, 3), [f"{provider}-vision-verifier"], confidence,
        [], observed, reason, confidence, {
            "vlm_verification": {"available": True, "score": round(score, 3), "confidence": confidence,
                                 "provider": provider, "model": model, "calibrated": False,
                                 "method": "independent_image_question_with_batched_claims"},
        }, diagnosis,
        ("CORRECT" if status == "SUPPORTED" else "INCORRECT" if status == "CONTRADICTED" else "AMBIGUOUS")
        if claim.type == "attribute" else None,
    )


def verify(image_path: str, claims: list[Claim], provider: str = "openai") -> list[Evidence]:
    """Verify typed claims in one separate VLM call against the image.

    The verifier receives only the atomic claims, not the generator's prose or
    reasoning. Its self-reported confidence is recorded as uncalibrated evidence;
    it is not represented as token probability or calibrated truth probability.
    """
    if not claims:
        return []
    claim_rows = [{
        "claim_id": claim.id,
        "claim_type": claim.type,
        "subject": claim.subject,
        "predicate": claim.attribute or claim.type,
        "value": claim.value,
        "object": claim.object,
    } for claim in claims]
    prompt = (
        "You are the independent visual verifier in a VLM reliability research system. "
        "Inspect the attached image yourself. Do not infer that a claim is true because it was supplied, "
        "and do not assume any other claim is true. Verify each atomic claim directly from visible evidence. "
        "For an attribute claim, check that exact attribute on that exact subject (entity-attribute binding). "
        "For quantity, count visible instances and say when occlusion makes a count uncertain. "
        "For a relation, assess the stated relation from the image; distinguish semantic from merely spatial relations. "
        "Use AMBIGUOUS when the image does not provide enough evidence; absence from your attention is not proof of absence. "
        "Return ONLY valid JSON with this shape: {\"verifications\":[{\"claim_id\":\"...\","
        "\"status\":\"SUPPORTED|CONTRADICTED|UNSUPPORTED|AMBIGUOUS\",\"observed_value\":null,"
        "\"confidence\":0.0,\"error_type\":null,\"reason\":\"short image-grounded explanation\"}]}. "
        "Confidence is your uncalibrated estimate from 0 to 1, not a token probability. Include exactly one row per input claim. "
        "Allowed error_type values: OBJECT_HALLUCINATION, ATTRIBUTE_ERROR, ATTRIBUTE_BINDING_ERROR, QUANTITY_ERROR, "
        "RELATION_ERROR, UNSUPPORTED_CLAIM, CONTRADICTED_CLAIM, AMBIGUOUS_CLAIM, MULTI_CLAIM_CONTRADICTION, or null.\n\n"
        f"ATOMIC CLAIMS TO VERIFY:\n{json.dumps(claim_rows, ensure_ascii=False)}"
    )
    response = run_vlm_task(image_path, prompt, provider)
    if not response.get("response"):
        reason = response.get("error") or "The verifier returned an empty response."
        return [_evidence(claim, None, provider, response.get("model", ""), reason) for claim in claims]
    rows = {str(row.get("claim_id")): row for row in _parse_response(response["response"])
            if isinstance(row, dict) and row.get("claim_id") is not None}
    return [_evidence(claim, rows.get(claim.id), provider, response.get("model", "")) for claim in claims]
