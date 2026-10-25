"""Text correction driven only by per-claim CORRECT actions (paper Sec. IV-E.2).

* binding error  -> replace the attribute with the value observed on the same
  region; two mutually exchanged attributes are recorded as a swap;
* quantity error -> replace the count with the detected count;
* hallucinated object (no detections) -> delete the phrase, or the sentence
  when the object is its subject; never substitute without evidence.
Everything else, including flagged (ABSTAIN) claims, is left untouched.
"""
from __future__ import annotations

import re

from claims.vocab import WORD_FOR_NUMBER, surface_forms
from core.schemas import Candidate, Claim

_STOP = r"(?!(?:and|or|is|are|was|were|the|a|an)\b)"
_ADJ = rf"(?:{_STOP}[a-z-]+\s+){{0,2}}"
_DET = r"(?:(?:a|an|the|some|two|three|four|five|several|many|one)\s+)?"
_ATTACH = r"(?:holding|carrying|with|wearing|riding|next to|near|beside|and|on|in|under|behind)"
_NUM = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})"


def _forms(claim: Claim) -> str:
    forms = [claim.surface] if claim.surface else []
    forms += surface_forms(claim.subject)
    return "|".join(re.escape(f) for f in sorted(set(filter(None, forms)), key=len, reverse=True))


def _match_case(original: str, replacement: str) -> str:
    return replacement[:1].upper() + replacement[1:] if original[:1].isupper() else replacement


def _attribute_spans(text: str, claim: Claim, new: str) -> list[tuple[int, int, str]]:
    old, forms = re.escape(str(claim.value)), _forms(claim)
    spans = []
    for pattern in (rf"\b({old})(\s+(?:[a-z-]+\s+)?)(?:{forms})\b",
                    rf"\b(?:{forms})\s+(?:that\s+|which\s+)?(?:is|are|was|were|looks|appears)\s+(?:(?:mostly|bright|dark|light)\s+)?({old})\b"):
        for m in re.finditer(pattern, text, flags=re.I):
            spans.append((m.start(1) if m.lastindex else m.start(), m.end(1), _match_case(m.group(1), new)))
    return spans


def _quantity_spans(text: str, claim: Claim, count: int) -> list[tuple[int, int, str]]:
    forms = _forms(claim)
    word = WORD_FOR_NUMBER.get(count, str(count))
    return [(m.start(1), m.end(1), _match_case(m.group(1), word))
            for m in re.finditer(rf"\b({_NUM})\s+(?:[a-z-]+\s+)?(?:{forms})\b", text, flags=re.I)]


def _clean(text: str) -> str:
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([,.;!?])", r"\1", text)
    text = re.sub(r",\s*([.;!?])", r"\1", text)
    text = re.sub(r"\b(and|or|with)\s*([.;!?])", r"\2", text)
    text = re.sub(r"([.!?])\s*[,;]\s*", r"\1 ", text)
    return text.strip(" ,;")


def _sentences(text: str) -> list[str]:
    return [s for s in re.findall(r"[^.!?]+[.!?]?", text) if s.strip()]


def delete_object(text: str, claim: Claim) -> str:
    """Remove a hallucinated object's phrase; drop the sentence if it is the subject."""
    forms = _forms(claim)
    noun = rf"{_DET}{_ADJ}(?:{forms})\b"
    out = []
    for sentence in _sentences(text):
        if not re.search(rf"\b(?:{forms})\b", sentence, flags=re.I):
            out.append(sentence); continue
        # Subject position: "A surfboard leans ...", "There is a surfboard ...".
        # A coordinated subject ("A dog and a cat sit") keeps the sentence and loses one item.
        if re.match(rf"\s*(?:there\s+(?:is|are)\s+|in\s+the\s+\w+\s*,?\s*)?{noun}(?!\s*(?:,|and\b|or\b))", sentence, flags=re.I):
            continue
        edited = sentence
        for pattern in (rf",?\s+{_ATTACH}\s+{noun}",              # "... holding a surfboard"
                        rf",\s*{noun}(?=\s*(?:,|and\b))",          # "a dog, a cat, and ..." middle item
                        rf"\s*{noun}\s*,?\s+and\s+"):              # first item "a dog and a cat"
            candidate = re.sub(pattern, " " if pattern.startswith(r"\s*") else "", edited, count=1, flags=re.I)
            if candidate != edited:
                edited = candidate; break
        if re.search(rf"\b(?:{forms})\b", edited, flags=re.I) or len(edited.split()) < 3:
            continue  # could not remove the phrase cleanly: drop the sentence
        edited = edited.strip()
        out.append(edited[:1].upper() + edited[1:])
    return _clean(" ".join(s.strip() for s in out))


def correct(candidate: Candidate) -> None:
    text, diagnoses = candidate.text, []
    claims = {c.id: c for c in candidate.claims}
    evidence = {e.claim_id: e for e in candidate.evidence}
    actions = candidate.claim_actions or {}
    candidate.action_details = {}
    corrections = [(claims[cid], evidence.get(cid)) for cid, action in actions.items() if action == "CORRECT" and cid in claims]

    # Replacements are located on the original text and applied together, so a
    # swap (blue shirt/red jeans -> red shirt/blue jeans) cannot cascade.
    spans: list[tuple[int, int, str]] = []
    attribute_fixes = {c.id: (c, str(e.verified_value)) for c, e in corrections if c.type == "attribute" and e and e.verified_value}
    for cid, (claim, new) in attribute_fixes.items():
        partner = next((other for oid, (other, other_new) in attribute_fixes.items()
                        if oid != cid and other.attribute == claim.attribute and other_new == str(claim.value) and new == str(other.value)), None)
        candidate.action_details[cid] = f"swap:{claim.subject}<->{partner.subject}" if partner else f"replace:{claim.value}->{new}"
        spans += _attribute_spans(text, claim, new)
        diagnoses.append("ATTRIBUTE_BINDING_ERROR")
    for claim, ev in corrections:
        if claim.type == "quantity" and ev and ev.verified_value:
            spans += _quantity_spans(text, claim, int(ev.verified_value))
            candidate.action_details[claim.id] = f"recount:{claim.value}->{ev.verified_value}"
            diagnoses.append("QUANTITY_ERROR")
    taken: list[tuple[int, int]] = []
    for start, end, new in sorted(spans, key=lambda s: s[0]):
        if all(end <= a or start >= b for a, b in taken):
            taken.append((start, end))
    for start, end, new in sorted((s for s in spans if (s[0], s[1]) in taken), key=lambda s: -s[0]):
        text = text[:start] + new + text[end:]

    for claim, _ in corrections:
        if claim.type == "object":
            updated = delete_object(text, claim)
            if updated.strip():
                text = updated
            candidate.action_details[claim.id] = "delete"
            diagnoses.append("OBJECT_HALLUCINATION")

    for cid, action in actions.items():
        if action == "ABSTAIN":
            ev = evidence.get(cid)
            diagnoses.append("AMBIGUOUS_CLAIM" if ev is None or ev.status == "AMBIGUOUS" else "UNSUPPORTED_CLAIM")
            candidate.action_details.setdefault(cid, "flag")
    candidate.corrected_text = text.strip() or candidate.text
    candidate.diagnosis = sorted(set(diagnoses)) or ["NO_STRONG_ERROR"]
