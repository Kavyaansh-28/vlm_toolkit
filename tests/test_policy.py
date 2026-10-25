"""Eq. 3 and the per-claim decision policy (paper Sec. IV-D, IV-E)."""
from claims.extractor import extract
from core.config import PipelineConfig
from core.policy import claim_action, select
from core.schemas import Candidate, Claim, Evidence
from reliability.engine import agreement, score

CFG = PipelineConfig(lo=.3, hi=.7, rerank_threshold=.5, grounding_threshold=.3,
                     weights={"verification": .6, "probability": .2, "agreement": .2})


def _cand(cid, text, values, probability=None):
    claims = extract(text)
    c = Candidate(cid, text, "test", claims, probability=probability, probability_available=probability is not None)
    c.evidence = [Evidence(cl.id, "SUPPORTED", values.get(cl.subject, .9), ["t"], evidence_quality=1) for cl in claims]
    return c


def test_agreement_unavailable_for_single_candidate():
    c = _cand("a", "A dog.", {})
    agreement([c])
    assert c.agreement_available is False and c.agreement == 0.0


def test_agreement_counts_only_other_candidates():
    a, b, c = _cand("a", "A dog and a cat.", {}), _cand("b", "A dog.", {}), _cand("c", "A dog.", {})
    agreement([a, b, c])
    assert a.agreement == .5 and b.agreement == 1.0


def test_equation_3_weighted_sum():
    c = _cand("a", "A dog.", {"dog": .9}, probability=.8)
    c.agreement, c.agreement_available = 1.0, True
    score(c, CFG)
    assert c.reliability == round(.6 * .9 + .2 * .8 + .2 * 1.0, 3) == .9


def test_unavailable_terms_redistributed():
    c = _cand("a", "A dog.", {"dog": .9})
    agreement([c]); score(c, CFG)
    assert c.reliability == .9  # only verification is available


def test_claim_actions():
    obj = Claim("o", "object", "dog")
    attr = Claim("a", "attribute", "car", value="blue", attribute="color")
    rel = Claim("r", "relation", "dog", value="left_of", object="cat")
    ev = lambda v, **kw: Evidence("x", kw.pop("status", "SUPPORTED"), v, ["t"], evidence_quality=1, **kw)
    assert claim_action(.8, ev(.8), obj, CFG) == "ACCEPT"
    assert claim_action(.0, ev(0, status="UNSUPPORTED"), obj, CFG) == "CORRECT"
    assert claim_action(.5, ev(.5), obj, CFG) == "ABSTAIN"
    assert claim_action(.05, ev(.05, status="CONTRADICTED", verified_value="red"), attr, CFG) == "CORRECT"
    assert claim_action(.05, ev(.05, status="UNSUPPORTED"), attr, CFG) == "ABSTAIN"  # no substitute evidence
    assert claim_action(.0, ev(0, status="CONTRADICTED"), rel, CFG) == "ABSTAIN"
    assert claim_action(None, Evidence("x", "AMBIGUOUS", .5, ["t"], evidence_quality=0), obj, CFG) == "ABSTAIN"


def test_object_only_ablation_accepts_unverified_attributes():
    attr = Claim("a", "attribute", "car", value="blue", attribute="color")
    assert claim_action(None, None, attr, CFG.with_overrides(attribute_verifier=False)) == "ACCEPT"
    assert claim_action(None, None, attr, CFG) == "ABSTAIN"


def test_per_type_thresholds():
    cfg = CFG.with_overrides(thresholds={"attribute": (.15, .4)})
    attr = Claim("a", "attribute", "car", value="red", attribute="color")
    assert claim_action(.45, Evidence("a", "SUPPORTED", .45, ["t"], evidence_quality=1), attr, cfg) == "ACCEPT"
    assert claim_action(.45, Evidence("a", "SUPPORTED", .45, ["t"], evidence_quality=1), attr, CFG) == "ABSTAIN"


def _scored(cid, reliability, actions):
    c = Candidate(cid, "t", "m")
    c.reliability, c.claim_actions = reliability, actions
    return c


def test_rerank_only_when_top_below_threshold_and_another_passes():
    chosen, decision, _ = select([_scored("1", .3, {"a": "ACCEPT"}), _scored("2", .8, {"a": "ACCEPT"})], CFG)
    assert (chosen, decision) == (1, "RERANK")
    chosen, decision, _ = select([_scored("1", .6, {"a": "ACCEPT"}), _scored("2", .9, {"a": "ACCEPT"})], CFG)
    assert (chosen, decision) == (0, "ACCEPT")


def test_abstain_when_no_reliable_candidate_and_nothing_to_fix():
    _, decision, _ = select([_scored("1", .2, {"a": "ABSTAIN"}), _scored("2", .3, {"a": "ABSTAIN"})], CFG)
    assert decision == "ABSTAIN"


def test_correction_beats_low_reliability():
    _, decision, _ = select([_scored("1", .4, {"a": "ACCEPT", "b": "CORRECT"})], CFG)
    assert decision == "CORRECT"


def test_reliability_ablation_never_reranks():
    chosen, decision, _ = select([_scored("1", .1, {"a": "ACCEPT"}), _scored("2", .9, {"a": "ACCEPT"})], CFG.with_overrides(reliability=False))
    assert chosen == 0 and decision == "ACCEPT"
