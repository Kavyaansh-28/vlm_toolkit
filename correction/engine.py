from __future__ import annotations
import re
from core.schemas import Candidate

def correct(candidate: Candidate) -> None:
    text, diagnoses = candidate.text, []
    claims = {c.id: c for c in candidate.claims}
    for item in candidate.evidence:
        claim = claims[item.claim_id]
        # Unsupported or ambiguous is not proof of an error: never delete/correct
        # a claim without a contradicted claim-level signal.
        if item.status == "CONTRADICTED" and item.diagnosis == "OBJECT_HALLUCINATION":
            diagnoses.append("OBJECT_HALLUCINATION")
            text = re.sub(r"(?:,?\s*(?:and\s+)?(?:a|an|the)?\s*" + re.escape(claim.subject) + r"s?)\b", "", text, flags=re.I)
        elif item.status == "CONTRADICTED" and item.diagnosis == "ATTRIBUTE_BINDING_ERROR" and item.verified_value:
            diagnoses.append("ATTRIBUTE_BINDING_ERROR")
            text = re.sub(r"\b(red|blue|green|yellow|black|white|orange|brown|gray|grey|purple|pink)\s+("+re.escape(claim.subject)+r"s?)\b", str(item.verified_value)+r" \2", text, flags=re.I)
        elif item.status == "CONTRADICTED" and item.diagnosis == "QUANTITY_ERROR" and item.verified_value is not None:
            diagnoses.append("QUANTITY_ERROR")
            text = re.sub(r"\b(one|two|three|four|five|\d+)\s+"+re.escape(claim.subject)+r"s?\b", f"{item.verified_value} {claim.subject}{'s' if item.verified_value != 1 else ''}", text, flags=re.I)
        elif item.status == "CONTRADICTED" and item.diagnosis == "RELATION_ERROR":
            diagnoses.append("RELATION_ERROR")
        elif item.status == "AMBIGUOUS":
            diagnoses.append("AMBIGUOUS_CLAIM")
        elif item.status == "UNSUPPORTED":
            diagnoses.append("UNSUPPORTED_CLAIM")
    candidate.corrected_text = re.sub(r"\s{2,}", " ", text).strip(" ,") or candidate.text
    candidate.diagnosis = sorted(set(diagnoses)) or ["NO_STRONG_ERROR"]
