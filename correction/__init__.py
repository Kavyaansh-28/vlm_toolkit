"""Correction package; includes the legacy row-based helper for compatibility."""
from __future__ import annotations
import re

def corrected_response(original: str, rows: list[dict]) -> str:
    """Apply conservative legacy corrections used by the original MVP tests."""
    result = original
    for row in rows:
        obj, status = row["object"], row["status"]
        if status == "INCORRECT" and row.get("verified_value"):
            result = re.sub(r"\b(red|blue|green|yellow|black|white|orange|brown|gray|grey|purple|pink)\s+(" + re.escape(obj) + r"s?)\b", f"{row['verified_value']} \\2", result, flags=re.I)
        elif status == "NOT VERIFIED":
            candidate = re.sub(r"(?:,?\s*(?:and\s+)?(?:a|an|the)?\s*" + re.escape(obj) + r"s?)\b", "", result, flags=re.I)
            if candidate.strip(" .,;!"): result = candidate
    return re.sub(r",\s*([.!])", r"\1", re.sub(r"\s{2,}", " ", result)).strip() or original
