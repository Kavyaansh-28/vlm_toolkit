"""Conservative, explainable claim decomposition for objects, attributes, counts and relations.

Rule-based by design (deterministic benchmark runs); an optional LLM extractor
in ``claims.llm_extractor`` can add claims for live demos.
"""
from __future__ import annotations

import hashlib
import re

from claims.vocab import (COLOR_ALIASES, COLORS, MATERIAL_ALIASES, MATERIALS, NUMBER_WORDS,
                          find_objects, to_class)
from core.schemas import Claim

RELATIONS = {"next to": "next_to", "beside": "next_to", "near": "near", "left of": "left_of",
             "right of": "right_of", "above": "above", "below": "below", "under": "below",
             "underneath": "below", "on top of": "above"}
ATTRIBUTE_WORDS = {**{c: ("color", c) for c in COLORS}, **{k: ("color", v) for k, v in COLOR_ALIASES.items()},
                   **{m: ("material", m) for m in MATERIALS}, **{k: ("material", v) for k, v in MATERIAL_ALIASES.items()}}
_ATTR = "|".join(sorted(ATTRIBUTE_WORDS, key=len, reverse=True))
_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_WORD = r"[a-z][a-z-]*"


def _sentences(text: str) -> list[tuple[str, int]]:
    return [(m.group(0), m.start()) for m in _SENTENCE.finditer(text) if m.group(0).strip()]


def extract(text: str) -> list[Claim]:
    out: list[Claim] = []
    seen: set[tuple] = set()

    def add(kind: str, subject: str, sentence: str, **kwargs):
        key = (kind, subject, kwargs.get("attribute"), str(kwargs.get("value")), kwargs.get("object"), kwargs.get("instance_id"))
        if key in seen: return
        seen.add(key)
        stable = hashlib.sha1(repr(key).encode("utf-8")).hexdigest()[:10]
        out.append(Claim(f"C-{stable}", kind, subject, text=sentence.strip(), **kwargs))

    for sentence, _ in _sentences(text):
        lower = sentence.lower()
        mentions = find_objects(sentence, include_extra=True)
        for cls, start, end in mentions:
            add("object", cls, sentence, surface=lower[start:end])

        # Attribute bindings: "<attr> [and <attr>] [adj] <obj>" and "<obj> (that) is <attr>".
        for cls, start, end in mentions:
            surface = lower[start:end]
            before = lower[:start]
            pre = re.search(rf"\b({_ATTR})(?:\s*(?:,|and)\s*({_ATTR}))?\s+(?:({_WORD})\s+)?$", before)
            if pre and (pre.group(3) is None or pre.group(3) not in {"and", "or", "a", "an", "the", "with", "of", "in", "on"}):
                for word in filter(None, (pre.group(1), pre.group(2))):
                    kind, value = ATTRIBUTE_WORDS[word]
                    add("attribute", cls, sentence, attribute=kind, value=value, surface=surface)
            post = re.match(rf"\s+(?:that\s+|which\s+)?(?:is|are|was|were|looks|appears)\s+(?:(?:mostly|bright|dark|light)\s+)?({_ATTR})(?:\s+and\s+({_ATTR}))?\b", lower[end:])
            if post:
                for word in filter(None, (post.group(1), post.group(2))):
                    kind, value = ATTRIBUTE_WORDS[word]
                    add("attribute", cls, sentence, attribute=kind, value=value, surface=surface)

        # Counts: number words / digits directly before an object phrase (one adjective allowed).
        for cls, start, end in mentions:
            count = re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})\s+(?:" + _WORD + r"\s+)?$", lower[:start])
            if count:
                word = count.group(1)
                value = int(word) if word.isdigit() else NUMBER_WORDS[word]
                add("quantity", cls, sentence, value=value, surface=lower[start:end])

        # Spatial relations between consecutive object mentions within the sentence.
        for i, (cls, start, end) in enumerate(mentions):
            for target, t_start, t_end in mentions[i + 1:]:
                between = lower[end:t_start]
                for phrase, relation in sorted(RELATIONS.items(), key=lambda kv: -len(kv[0])):
                    if re.search(r"\b" + phrase + r"\b", between) and len(between.split()) <= 8:
                        if cls != target:
                            add("relation", cls, sentence, value=relation, object=target, surface=lower[start:end])
                        break
                break  # only the nearest following object is the relation target

    # Attribute/quantity claims entail object presence; keep explicit object nodes.
    represented = {c.subject for c in out if c.type == "object"}
    for claim in list(out):
        if claim.type in {"attribute", "quantity"} and claim.subject not in represented:
            add("object", claim.subject, claim.text, surface=claim.surface)
            represented.add(claim.subject)
    return out


def normalize(phrase: str) -> str:
    return to_class(phrase) or phrase.strip().lower()
