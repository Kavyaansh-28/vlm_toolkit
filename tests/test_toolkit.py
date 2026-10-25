from claims.extractor import extract
from core.config import load_config
from core.schemas import Candidate, Evidence
from reliability.engine import agreement, score


def test_decomposer_includes_quantity_and_relation():
    claims = extract("Two cars are left of a bicycle.")
    assert any(c.type == "quantity" and c.value == 2 for c in claims)
    assert any(c.type == "relation" and c.value == "left_of" for c in claims)


def test_claim_level_agreement_and_reliability():
    claims_a, claims_b = extract("A red car."), extract("A red car.")
    a = Candidate("a", "A red car.", "test", claims_a, [Evidence(c.id, "SUPPORTED", .9, ["test"], evidence_quality=1) for c in claims_a])
    b = Candidate("b", "A red car.", "test", claims_b, [Evidence(c.id, "SUPPORTED", .9, ["test"], evidence_quality=1) for c in claims_b])
    agreement([a, b]); score(a, load_config(tuned="__none__"))
    assert a.agreement == 1.0 and a.agreement_available and a.reliability >= .9
