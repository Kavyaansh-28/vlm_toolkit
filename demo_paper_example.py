"""Reproducible paper Table IV correction demonstration.

This is an evidence fixture, not a claimed live Grounding DINO experiment. It
exercises the same decision and correction classes used in production and is
useful for a deterministic project presentation when model weights are absent.
"""
from __future__ import annotations
import json
from claims.extractor import extract
from correction.engine import correct
from core.schemas import Candidate, Evidence
from reliability.engine import agreement, score

text = "A person in a blue shirt and red jeans stands on the beach holding a surfboard."
claims = extract(text)
out = []
for claim in claims:
    status, value, diagnosis, value_score = "SUPPORTED", None, None, .9
    if claim.subject == "surfboard" and claim.type == "object": status, diagnosis, value_score = "UNSUPPORTED", "UNSUPPORTED_CLAIM", 0.0
    if claim.subject == "shirt" and claim.type == "attribute": status, value, diagnosis, value_score = "CONTRADICTED", "red", "ATTRIBUTE_BINDING_ERROR", .05
    if claim.subject == "jeans" and claim.type == "attribute": status, value, diagnosis, value_score = "CONTRADICTED", "blue", "ATTRIBUTE_BINDING_ERROR", .05
    out.append(Evidence(claim.id, status, value_score, ["paper-table-iv-fixture"], verified_value=value, evidence_quality=1.0, diagnosis=diagnosis))
candidate = Candidate("paper-example", text, "evidence-fixture", claims, out)
agreement([candidate]); score(candidate, {"verification": .6, "probability": .2, "agreement": .2}, .7, .3); correct(candidate)
print(json.dumps(candidate.export(), indent=2))
