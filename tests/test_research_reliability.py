from __future__ import annotations

from claims.extractor import extract
from core.config import load_config
from core.policy import assign_actions
from core.schemas import Candidate, Evidence
from correction.engine import correct
from evaluation.metrics import classification_metrics
from reliability.engine import agreement, score
from verification.attribute_verifier import AttributeProbeResult, AttributeVerifier
from verification.grounding import GroundingResult
from verification.object_verifier import ObjectVerifier


class FakeGrounder:
    def __init__(self, boxes, scores, available=True): self.boxes, self.scores, self.available = boxes, scores, available
    def detect(self, image_path, object_name):
        return GroundingResult(object_name, self.boxes, self.scores, self.available, "offline" if not self.available else "", "fake-grounding-dino")


class FakeProbe:
    def __init__(self, values): self.values = values
    def classify(self, crop, attribute_type, labels, object_name=""): return AttributeProbeResult(self.values, backend="fake-clip")


def test_object_score_is_max_grounding_confidence():
    evidence = ObjectVerifier(FakeGrounder([[0,0,4,4], [4,4,8,8]], [.12, .83])).verify_object("car", "unused.png", "c1")
    assert evidence.status == "SUPPORTED" and evidence.score == .83
    assert evidence.signals["open_vocabulary_grounding"]["equation"] == "s_obj(o)=max_{b in B_o} d_b"
    assert evidence.boxes == [[4, 4, 8, 8]]  # only boxes above the support threshold are shown


def test_below_threshold_score_is_kept_not_clipped():
    evidence = ObjectVerifier(FakeGrounder([[0, 0, 4, 4]], [.18]), threshold=.30).verify_object("dog", "unused.png", "c1")
    assert evidence.status == "UNSUPPORTED" and evidence.score == .18 and evidence.boxes == []


def test_missing_grounding_is_explicitly_unsupported():
    evidence = ObjectVerifier(FakeGrounder([], [])).verify_object("dog", "unused.png", "c1")
    assert evidence.status == "UNSUPPORTED" and evidence.score == 0 and evidence.boxes == []


def test_attribute_binding_uses_object_crop_and_equation(tmp_path):
    from PIL import Image
    image = tmp_path / "scene.png"; Image.new("RGB", (12, 12), "red").save(image)
    evidence = AttributeVerifier(FakeProbe({"red": .94, "blue": .05})).verify(str(image), [[1,1,10,10]], [.9], "color", "blue", "c1", "car")
    # score is d_b * P(blue | crop), while red is an alternative on that same crop.
    assert evidence.status == "CONTRADICTED" and evidence.verified_value == "red" and evidence.score == .045
    assert "s_attr(o,a)=max_{b in B_o} d_b*P(a|crop_b)" in evidence.signals["region_attribute_probe"]["equation"]
    assert evidence.region_crop and evidence.region_crop.startswith("data:image/jpeg;base64,")


def test_pink_is_a_reachable_colour(tmp_path):
    from PIL import Image
    image = tmp_path / "scene.png"; Image.new("RGB", (12, 12), "pink").save(image)
    evidence = AttributeVerifier(FakeProbe({"pink": .9, "blue": .02})).verify(str(image), [[1,1,10,10]], [.9], "color", "blue", "c1", "shirt")
    assert evidence.status == "CONTRADICTED" and evidence.verified_value == "pink"


def test_material_probe_is_supported(tmp_path):
    from PIL import Image
    image = tmp_path / "scene.png"; Image.new("RGB", (12, 12), "brown").save(image)
    evidence = AttributeVerifier(FakeProbe({"wooden": .8, "metal": .1})).verify(str(image), [[1,1,10,10]], [.9], "material", "wooden", "c1", "bench")
    assert evidence.status == "SUPPORTED" and abs(evidence.score - .72) < 1e-9


def test_unavailable_visual_backend_stays_ambiguous():
    evidence = ObjectVerifier(FakeGrounder([], [], available=False)).verify_object("dog", "unused.png", "c1")
    assert evidence.status == "AMBIGUOUS" and evidence.evidence_quality == 0


def test_binding_correction_and_candidate_agreement():
    claims = extract("A blue car.")
    candidate = Candidate("a", "A blue car.", "test", claims)
    candidate.evidence = [Evidence(next(c.id for c in claims if c.type == "object"), "SUPPORTED", .9, ["grounding-dino"], evidence_quality=1),
                          Evidence(next(c.id for c in claims if c.type == "attribute"), "CONTRADICTED", .05, ["grounding-dino", "clip"], verified_value="red", evidence_quality=1, diagnosis="ATTRIBUTE_BINDING_ERROR")]
    cfg = load_config(tuned="__none__")
    agreement([candidate]); score(candidate, cfg); assign_actions(candidate, cfg); correct(candidate)
    assert "red car" in candidate.corrected_text.lower()


def test_unavailable_token_probability_weight_is_redistributed():
    candidate = Candidate("x", "A car.", "test", extract("A car."))
    candidate.evidence = [Evidence(candidate.claims[0].id, "SUPPORTED", .8, ["test"], evidence_quality=1)]
    score(candidate, {"verification": .5, "probability": .25, "agreement": .25})
    assert candidate.probability is None and candidate.probability_available is False and candidate.reliability == .8


def test_calibration_refuses_tiny_samples():
    result = classification_metrics([{"expected_reliable": True, "reliability": .8}])
    assert result["available"] is True and result["calibration_available"] is False and result["ece"] is None
