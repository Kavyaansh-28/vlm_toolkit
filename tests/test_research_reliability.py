import json

from claims.extractor import extract
from claims.graph import graph_data
from core.schemas import Candidate
from correction.engine import correct
from evaluation.metrics import classification_metrics
from reliability.engine import agreement, score
from verification.service import verify


def _respond(monkeypatch, claims, rows, prompts=None):
    payload = json.dumps({"verifications": [
        {"claim_id": claim.id, **rows.get(claim.id, {
            "status": "AMBIGUOUS", "observed_value": None, "confidence": .8,
            "reason": "Insufficient visible evidence.",
        })} for claim in claims
    ]})

    def fake_call(image_path, prompt, provider):
        if prompts is not None:
            prompts.append((prompt, provider))
        return {"response": payload, "model": f"{provider}-vision-test"}

    monkeypatch.setattr("verification.service.run_vlm_task", fake_call)


def test_stable_claim_ids_and_graph_binding():
    text = "A blue car beside a red bicycle."
    claims = extract(text)
    assert [x.id for x in claims] == [x.id for x in extract(text)]
    graph = graph_data(claims)
    assert any(e["label"] == "color" and e["claim_id"] for e in graph["edges"])
    assert {c["type"] for c in graph["claims"]} >= {"object", "attribute", "relation"}


def test_vlm_verifies_attribute_binding_independently(monkeypatch):
    text = "A blue car and a red bicycle."
    claims = extract(text)
    attributes = [claim for claim in claims if claim.type == "attribute"]
    prompts = []
    rows = {
        attributes[0].id: {"status": "CONTRADICTED", "observed_value": "red", "confidence": .93,
                          "error_type": "ATTRIBUTE_BINDING_ERROR", "reason": "The car appears red."},
        attributes[1].id: {"status": "CONTRADICTED", "observed_value": "blue", "confidence": .91,
                          "error_type": "ATTRIBUTE_BINDING_ERROR", "reason": "The bicycle appears blue."},
    }
    _respond(monkeypatch, claims, rows, prompts)
    evidence = verify("unused.png", claims, "gemini")
    by_id = {item.claim_id: item for item in evidence}
    assert by_id[attributes[0].id].status == "CONTRADICTED"
    assert by_id[attributes[0].id].diagnosis == "ATTRIBUTE_BINDING_ERROR"
    assert by_id[attributes[0].id].verified_value == "red"
    assert by_id[attributes[0].id].score == .07
    assert "A blue car and a red bicycle" not in prompts[0][0]
    assert prompts[0][1] == "gemini"


def test_ambiguous_verification_does_not_fabricate_evidence(monkeypatch):
    claims = extract("A dog.")
    _respond(monkeypatch, claims, {})
    evidence = verify("unused.png", claims, "openai")
    assert evidence and all(item.status == "AMBIGUOUS" for item in evidence)
    assert all(item.evidence_quality == .8 for item in evidence)
    assert all(item.boxes == [] for item in evidence)


def test_object_hallucination_corrects_only_with_contradiction(monkeypatch):
    text = "A person and a dog."
    claims = extract(text)
    dog = next(claim for claim in claims if claim.subject == "dog" and claim.type == "object")
    rows = {dog.id: {"status": "CONTRADICTED", "observed_value": None, "confidence": .9,
                     "error_type": "OBJECT_HALLUCINATION", "reason": "No dog is visible."}}
    _respond(monkeypatch, claims, rows)
    evidence = verify("unused.png", claims)
    candidate = Candidate("x", text, "test", claims, evidence)
    score(candidate, {"verification": .7, "agreement": .3, "probability": 0})
    assert candidate.decision == "CORRECT"
    correct(candidate)
    assert "dog" not in candidate.corrected_text.lower()
    assert "person" in candidate.corrected_text.lower()


def test_quantity_and_relation_are_checked_by_same_vlm_call(monkeypatch):
    claims = extract("Three cars are left of a bicycle.")
    quantity = next(claim for claim in claims if claim.type == "quantity")
    relation = next(claim for claim in claims if claim.type == "relation")
    rows = {
        quantity.id: {"status": "CONTRADICTED", "observed_value": 2, "confidence": .86,
                      "error_type": "QUANTITY_ERROR", "reason": "Two cars are visible."},
        relation.id: {"status": "SUPPORTED", "observed_value": "left_of", "confidence": .82,
                      "reason": "The cars are left of the bicycle."},
    }
    prompts = []
    _respond(monkeypatch, claims, rows, prompts)
    evidence = verify("unused.png", claims, "groq")
    assert len(prompts) == 1  # all claims are batched into one verifier call
    assert next(item for item in evidence if item.claim_id == quantity.id).diagnosis == "QUANTITY_ERROR"
    assert next(item for item in evidence if item.claim_id == relation.id).status == "SUPPORTED"


def test_reliability_vetoes_candidate_agreement_when_vlm_contradicts(monkeypatch):
    claims = extract("A blue car.")
    attr = next(claim for claim in claims if claim.type == "attribute")
    rows = {attr.id: {"status": "CONTRADICTED", "observed_value": "red", "confidence": .95,
                      "error_type": "ATTRIBUTE_BINDING_ERROR", "reason": "The car appears red."}}
    _respond(monkeypatch, claims, rows)
    evidence = verify("unused.png", claims)
    candidates = [Candidate("a", "A blue car.", "test", claims, evidence),
                  Candidate("b", "A blue car.", "test", claims, evidence)]
    agreement(candidates)
    score(candidates[0], {"verification": .7, "agreement": .3, "probability": 0})
    assert candidates[0].agreement == 1.0
    assert candidates[0].decision == "CORRECT"
    correct(candidates[0])
    assert "red car" in candidates[0].corrected_text.lower()


def test_unavailable_token_probability_weight_is_redistributed():
    from core.schemas import Evidence

    candidate = Candidate("x", "A car.", "test", evidence=[
        Evidence("c1", "SUPPORTED", .8, ["vision-verifier"], evidence_quality=1.0),
    ], agreement=0.0)
    score(candidate, {"verification": .5, "probability": .25, "agreement": .25})
    assert candidate.probability is None
    assert candidate.probability_available is False
    assert candidate.reliability == .6


def test_calibration_refuses_tiny_samples():
    result = classification_metrics([{"expected_reliable": True, "reliability": .8}])
    assert result["available"] is True
    assert result["calibration_available"] is False
    assert result["ece"] is None
