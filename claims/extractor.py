"""Conservative, explainable claim decomposition for objects, attributes, counts and relations."""
from __future__ import annotations
import re
import hashlib
from core.schemas import Claim
from claims import COLORS, COMMON_OBJECTS, normalize_object

RELATIONS = {"next to": "next_to", "beside": "next_to", "near": "near", "left of": "left_of", "right of": "right_of", "above": "above", "below": "below"}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

def extract(text: str) -> list[Claim]:
    lower, out, seen = text.lower(), [], set()
    def add(kind: str, subject: str, **kwargs):
        key = (kind, subject, kwargs.get("attribute"), str(kwargs.get("value")), kwargs.get("object"), kwargs.get("instance_id"))
        if key not in seen:
            seen.add(key)
            stable = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:10]
            out.append(Claim(f"C-{stable}", kind, subject, text=text, **kwargs))
    for color, obj in re.findall(r"\b(" + "|".join(COLORS) + r")\s+([a-z-]+)s?\b", lower):
        obj = normalize_object(obj)
        if obj in COMMON_OBJECTS: add("attribute", obj, attribute="color", value="gray" if color == "grey" else color)
    for obj in COMMON_OBJECTS:
        norm = normalize_object(obj)
        if re.search(r"\b" + re.escape(obj) + r"s?\b", lower): add("object", norm)
    for word, count in NUMBER_WORDS.items():
        for obj in COMMON_OBJECTS:
            if re.search(r"\b"+word+r"\s+"+re.escape(obj)+r"s?\b", lower): add("quantity", normalize_object(obj), value=count)
    object_pattern = "|".join(sorted(COMMON_OBJECTS, key=len, reverse=True))
    for phrase, relation in RELATIONS.items():
        match = re.search(r"\b(" + object_pattern + r")s?\b.*?\b" + re.escape(phrase) + r"\b.*?(?:a |an |the )?\b(" + object_pattern + r")s?\b", lower)
        if match:
            subject, obj = normalize_object(match.group(1)), normalize_object(match.group(2))
            if subject in COMMON_OBJECTS and obj in COMMON_OBJECTS: add("relation", subject, value=relation, object=obj)
    # An attribute claim entails object presence. Keep the explicit object node
    # so callers can distinguish attribute existence from object binding.
    represented = {c.subject for c in out if c.type == "object"}
    for claim in list(out):
        if claim.type in {"attribute", "quantity"} and claim.subject not in represented:
            add("object", claim.subject)
            represented.add(claim.subject)
    return out
