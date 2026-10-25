"""Claim vocabulary and a small dict-based view of the extractor."""
from __future__ import annotations

from claims.vocab import COLORS, MATERIALS, to_class


def normalize_object(value: str) -> str:
    """Canonical class for a phrase ("men" -> "person"); unknown words unchanged."""
    return to_class(value) or value.strip().lower()


def extract_claims(text: str) -> list[dict]:
    from .extractor import extract
    return [{"object": c.subject, "attribute": c.attribute, "value": c.value}
            for c in extract(text) if c.type in {"object", "attribute"}]
