"""Deterministic stand-in verifier for CI / pipeline smoke tests (no models).

Objects listed in FAKE_ABSENT are reported as not detected; every other object
is detected with score 0.8 and attributes are supported.  Never used for
reported results.
"""
from __future__ import annotations

from core.schemas import Claim, Evidence

FAKE_ABSENT = {"surfboard", "fire hydrant", "giraffe"}


def fake_verify(image_path: str, claims: list[Claim], attribute: bool = True) -> list[Evidence]:
    out = []
    for claim in claims:
        absent = claim.subject in FAKE_ABSENT
        if claim.type == "attribute" and not attribute:
            continue
        if claim.type == "object":
            out.append(Evidence(claim.id, "UNSUPPORTED" if absent else "SUPPORTED", 0.0 if absent else .8, ["fake"],
                                boxes=[] if absent else [[0, 0, 10, 10]], evidence_quality=1.0,
                                diagnosis="OBJECT_HALLUCINATION" if absent else None))
        else:
            out.append(Evidence(claim.id, "SUPPORTED", .6, ["fake"], boxes=[[0, 0, 10, 10]], evidence_quality=1.0))
    return out
