from claims.extractor import extract
from core.schemas import Candidate, Evidence
from reliability.engine import agreement, score

def test_decomposer_includes_quantity_and_relation():
    claims=extract("Two cars are left of a bicycle.")
    assert any(c.type == "quantity" and c.value == 2 for c in claims)
    assert any(c.type == "relation" and c.value == "left_of" for c in claims)

def test_claim_level_agreement_and_reliability():
    a=Candidate("a","A red car.","test",extract("A red car."),[Evidence("C1","VERIFIED",.9,["test"])])
    b=Candidate("b","A red car.","test",extract("A red car."),[Evidence("C1","VERIFIED",.9,["test"])])
    agreement([a,b]); score(a,{"verification":.7,"agreement":.3,"probability":0})
    assert a.agreement == 1.0 and a.reliability >= .8
