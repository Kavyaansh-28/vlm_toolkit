"""Conservative text-level correction using only verification evidence."""
from __future__ import annotations

import re


def corrected_response(original: str, rows: list[dict]) -> str:
    result = original
    for row in rows:
        obj, status = row["object"], row["status"]
        if status == "INCORRECT" and row.get("verified_value"):
            # Replace just the colour immediately attached to the verified object.
            result = re.sub(r"\b(red|blue|green|yellow|black|white|orange|brown|gray|grey|purple|pink)\s+(" + re.escape(obj) + r"s?)\b", f"{row['verified_value']} \\2", result, flags=re.I)
        elif status == "NOT VERIFIED":
            # Remove a simple list item; retain the original if removal would empty it.
            candidate = re.sub(r"(?:,?\s*(?:and\s+)?(?:a|an|the)?\s*" + re.escape(obj) + r"s?)\b", "", result, flags=re.I)
            if candidate.strip(" .,;!"):
                result = candidate
    result = re.sub(r"\s{2,}", " ", result)
    result = re.sub(r",\s*([.!])", r"\\1", result)
    return result.strip() or original
