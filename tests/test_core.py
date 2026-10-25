from claims import extract_claims, normalize_object
from core.config import load_config
from demo_paper_example import run_example


def test_extracts_colour_and_object():
    claims = extract_claims("There is a red car and a dog.")
    assert {"object": "car", "attribute": "color", "value": "red"} in claims
    assert {"object": "dog", "attribute": None, "value": None} in claims


def test_normalize_object_uses_chair_synonyms():
    assert normalize_object("men") == "person"
    assert normalize_object("motorbike") == "motorcycle"
    assert normalize_object("bus") == "bus"


def test_config_has_single_source_of_thresholds():
    cfg = load_config(tuned="__none__")
    assert cfg.lo < cfg.hi
    assert set(cfg.thresholds) >= {"object", "attribute"}
    assert abs(sum(cfg.weights.values()) - 1.0) < 1e-9


def test_paper_table_iv_example():
    result = run_example()
    assert result["corrected_text"] == "A person in a red shirt and blue jeans stands on the beach."
    actions = {next(c for c in result["claims"] if c["id"] == cid)["subject"] + ":" + next(c for c in result["claims"] if c["id"] == cid)["type"]: a
               for cid, a in result["claim_actions"].items()}
    assert actions["person:object"] == "ACCEPT"
    assert actions["surfboard:object"] == "CORRECT"
    assert actions["shirt:attribute"] == "CORRECT" and actions["jeans:attribute"] == "CORRECT"
    assert result["decision"] == "CORRECT"
    assert any(detail.startswith("swap:") for detail in result["action_details"].values())
