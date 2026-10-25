"""End-to-end pipeline with a fake verifier: selection, corrections, ablations."""
from core.config import PipelineConfig
from core.pipeline import process_candidates, rows_from_manual
from core.schemas import Claim, Evidence
from correction.engine import delete_object
from evaluation.ablations import ABLATIONS, ablation_config
from evaluation.fake import fake_verify

CFG = PipelineConfig(lo=.3, hi=.7, rerank_threshold=.5, grounding_threshold=.3,
                     weights={"verification": .6, "probability": .2, "agreement": .2},
                     thresholds={"attribute": (.15, .4)}, candidate_count=3)


def colour_verifier(observed: dict, absent=()):
    def verify(image_path, claims, attribute=True):
        out = []
        for c in claims:
            if c.type == "object":
                out.append(Evidence(c.id, "UNSUPPORTED" if c.subject in absent else "SUPPORTED", 0.0 if c.subject in absent else .9, ["f"], evidence_quality=1))
            elif c.type == "attribute" and attribute:
                truth = observed.get(c.subject)
                ok = truth is None or truth == c.value
                out.append(Evidence(c.id, "SUPPORTED" if ok else "CONTRADICTED", .8 if ok else .03, ["f"],
                                    verified_value=None if ok else truth, evidence_quality=1))
        return out
    return verify


def test_selected_candidate_first_and_rerank():
    rows = rows_from_manual("A giraffe and a surfboard on a fire hydrant. ||| A dog on a bench. ||| A dog near a bench.")
    out = process_candidates("x.png", rows, CFG, verify_fn=fake_verify)
    assert out[0].selected and out[0].id != "candidate-1" and out[0].decision == "RERANK"


def test_attribute_correction_and_object_only_ablation():
    rows = [{"response": "A man in a blue shirt sits on a bench."}]
    verify = colour_verifier({"shirt": "red"})
    full = process_candidates("x.png", rows, CFG.with_overrides(candidate_count=1), verify_fn=verify)[0]
    assert "red shirt" in full.corrected_text and full.decision == "CORRECT"
    ablated = process_candidates("x.png", rows, ablation_config("no_attribute_binding", CFG), verify_fn=verify)[0]
    assert "blue shirt" in ablated.corrected_text


def test_base_vlm_ablation_returns_uncorrected_text():
    rows = [{"response": "A dog with a surfboard."}]
    out = process_candidates("x.png", rows, ablation_config("base_vlm", CFG), verify_fn=fake_verify)
    assert out[0].corrected_text == "A dog with a surfboard." and out[0].decision == "ACCEPT"


def test_n_equals_1_uses_only_first_candidate():
    rows = rows_from_manual("A dog. ||| A cat. ||| A bird.")
    out = process_candidates("x.png", rows, ablation_config("n_equals_1", CFG), verify_fn=fake_verify)
    assert len(out) == 1 and out[0].agreement_available is False


def test_every_ablation_is_runnable():
    rows = rows_from_manual("A dog on a bench. ||| A dog.")
    for name in ABLATIONS:
        assert process_candidates("x.png", rows, ablation_config(name, CFG), verify_fn=fake_verify)


def _claim(subject, surface=None):
    return Claim("c", "object", subject, surface=surface or subject)


def test_delete_attachment_phrase():
    assert delete_object("A man holding a red surfboard stands on the sand.", _claim("surfboard")) == "A man stands on the sand."


def test_delete_list_items():
    assert delete_object("There is a dog, a cat, and a bench.", _claim("cat")) == "There is a dog, and a bench."
    assert delete_object("A dog and a cat sit on the grass.", _claim("dog")) == "A cat sit on the grass."


def test_delete_subject_sentence_and_synonyms():
    text = "A girl rides a horse. A giraffe stands behind the fence."
    assert delete_object(text, _claim("giraffe")) == "A girl rides a horse."
    assert delete_object("Two men play frisbee in the park. The grass is green.", _claim("person", "men")) == "The grass is green."


def test_delete_never_leaves_dangling_attachment():
    out = delete_object("A man holding a red umbrella stands near a fire hydrant.", _claim("fire hydrant"))
    assert "hydrant" not in out and not out.rstrip(".").endswith(("near", "stands near"))
