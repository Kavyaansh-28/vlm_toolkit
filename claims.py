"""Small, deliberately conservative claim extractor for the MVP."""
from __future__ import annotations

import re
from typing import Any

COLORS = ("red", "blue", "green", "yellow", "black", "white", "orange", "brown", "gray", "grey", "purple", "pink")
COMMON_OBJECTS = (
    "person", "man", "woman", "child", "dog", "cat", "car", "bicycle", "bike", "motorcycle",
    "bus", "truck", "boat", "bird", "horse", "bench", "chair", "table", "phone", "laptop",
    "bottle", "cup", "backpack", "umbrella", "surfboard", "shirt", "jeans", "pants", "hat",
)
ALIASES = {"bike": "bicycle", "automobile": "car", "grey": "gray", "man": "person", "woman": "person", "child": "person"}


def normalize_object(value: str) -> str:
    value = value.strip().lower()
    # Preserve singular classes that end in s (bus); remove s only when it is
    # actually a plural form in the supported vocabulary.
    if value not in COMMON_OBJECTS:
        plural = next((item for item in COMMON_OBJECTS if value == item + "s"), None)
        if plural:
            value = plural
    return ALIASES.get(value, value)


def extract_claims(text: str) -> list[dict[str, Any]]:
    """Extract colour/object pairs plus a small known-object vocabulary.

    This is intentionally not a general NLP parser; predictable demo behaviour is
    more useful here than opaque extraction failures.
    """
    text = text.lower()
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()

    color_pattern = r"\b(" + "|".join(COLORS) + r")\s+([a-z-]+)s?\b"
    for color, obj in re.findall(color_pattern, text):
        obj = normalize_object(obj)
        if obj in COMMON_OBJECTS or obj in {"person", "shirt", "jean"}:
            key = (obj, "color", ALIASES.get(color, color))
            if key not in seen:
                found.append({"object": obj, "attribute": "color", "value": key[2]})
                seen.add(key)

    for obj in COMMON_OBJECTS:
        if re.search(r"\b" + re.escape(obj) + r"s?\b", text):
            normalized = normalize_object(obj)
            if not any(item["object"] == normalized for item in found):
                key = (normalized, None, None)
                if key not in seen:
                    found.append({"object": normalized, "attribute": None, "value": None})
                    seen.add(key)
    return found
