"""Claim vocabulary and backward-compatible simple extractor."""
from __future__ import annotations
COLORS = ("red","blue","green","yellow","black","white","orange","brown","gray","grey","purple","pink")
COMMON_OBJECTS = ("person","man","woman","child","dog","cat","car","bicycle","bike","motorcycle","bus","truck","boat","bird","horse","bench","chair","table","phone","laptop","bottle","cup","backpack","umbrella","surfboard","shirt","jeans","pants","hat")
ALIASES={"bike":"bicycle","automobile":"car","grey":"gray","man":"person","woman":"person","child":"person"}
def normalize_object(value: str) -> str:
    value=value.strip().lower().rstrip("s"); return ALIASES.get(value,value)
def extract_claims(text: str) -> list[dict]:
    from .extractor import extract
    return [{"object":c.subject,"attribute":c.attribute,"value":c.value} for c in extract(text) if c.type in {"object","attribute"}]
