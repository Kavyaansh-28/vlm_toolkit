"""Reproducible paper Table IV correction demonstration.

This is an evidence fixture, not a claimed live Grounding DINO experiment. It
runs the production pipeline (extraction, Eq. 3 scoring, per-claim policy,
correction) on fixed verifier outputs, so it works without model weights.
"""
from __future__ import annotations

import json

from core.config import load_config
from core.pipeline import process_candidates
from core.schemas import Evidence

TEXT = "A person in a blue shirt and red jeans stands on the beach holding a surfboard."


def table_iv_verifier(image_path, claims, attribute=True):
    out = []
    for claim in claims:
        if claim.type == "object" and claim.subject == "surfboard":
            out.append(Evidence(claim.id, "UNSUPPORTED", 0.0, ["paper-table-iv-fixture"], evidence_quality=1.0,
                                diagnosis="OBJECT_HALLUCINATION", explanation="No detection in image."))
        elif claim.type == "attribute" and claim.subject in {"shirt", "jeans"}:
            observed = {"shirt": "red", "jeans": "blue"}[claim.subject]
            out.append(Evidence(claim.id, "CONTRADICTED", .05, ["paper-table-iv-fixture"], verified_value=observed, evidence_quality=1.0,
                                diagnosis="ATTRIBUTE_BINDING_ERROR", explanation=f"{claim.subject.title()} region is {observed}."))
        else:
            out.append(Evidence(claim.id, "SUPPORTED", .9, ["paper-table-iv-fixture"], evidence_quality=1.0, explanation="Confirmed."))
    return out


def run_example() -> dict:
    cfg = load_config().with_overrides(candidate_count=1)
    candidate = process_candidates("unused.png", [{"response": TEXT, "model": "evidence-fixture"}], cfg,
                                   verify_fn=table_iv_verifier)[0]
    return candidate.export()


if __name__ == "__main__":
    result = run_example()
    claims = {c["id"]: c for c in result["claims"]}
    print("Claim".ljust(28), "Action".ljust(9), "Detail")
    for claim_id, action in result["claim_actions"].items():
        c = claims[claim_id]
        label = f"{c['subject']} {c['type']}" + (f"={c['value']}" if c["value"] is not None else "")
        print(label.ljust(28), action.ljust(9), result["action_details"].get(claim_id, ""))
    print("\nDecision:", result["decision"], "| R =", result["reliability"])
    print("Original: ", result["text"])
    print("Corrected:", result["corrected_text"])
    if "--json" in __import__("sys").argv:
        print(json.dumps(result, indent=2))
