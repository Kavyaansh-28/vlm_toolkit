"""Process stage, POPE metrics, report and tuning on synthetic generation files."""
import json

from core.config import load_config
from evaluation.evaluator import evaluate, pope
from evaluation.process import parse_yes_no, process_file
from evaluation.reports import markdown, write_report
from evaluation.tune import main as tune_main, tune_thresholds
from evaluation.fake import fake_verify


def _pope_row(label, final, base=None, abstained=False):
    return {"label": label, "pope": {"base_answer": final if base is None else base, "final_answer": final, "abstained": abstained}}


def test_pope_metrics_hand_computed():
    rows = [_pope_row(True, True), _pope_row(False, True), _pope_row(False, False, base=True), _pope_row(True, False)]
    m = pope(rows)
    assert m["accuracy"] == .5 and m["precision"] == .5 and m["recall"] == .5 and m["yes_ratio"] == .5
    assert m["corrected_yes_to_no"] == 1


def test_parse_yes_no():
    assert parse_yes_no("Yes") and parse_yes_no("Yes, there is a dog.")
    assert not parse_yes_no("No") and not parse_yes_no("There is not a dog in the image.")


def _gen(tmp_path):
    gen = tmp_path / "gen"; gen.mkdir()
    pope_rows = [
        {"sample_id": "p1", "benchmark": "pope", "split": "random", "image_path": "x.png", "object": "dog", "label": True,
         "model": "m", "candidates": [{"text": "Yes", "probability": .9, "latency_ms": 100}]},
        {"sample_id": "p2", "benchmark": "pope", "split": "random", "image_path": "x.png", "object": "giraffe", "label": False,
         "model": "m", "candidates": [{"text": "Yes", "probability": .7, "latency_ms": 100}]},
        {"sample_id": "p3", "benchmark": "pope", "split": "random", "image_path": "x.png", "object": "cat", "label": False,
         "model": "m", "candidates": [{"text": "No", "probability": .8, "latency_ms": 100}]}]
    chair_rows = [{"sample_id": "c1", "benchmark": "chair", "split": "all", "image_path": "x.png", "gt_objects": ["dog", "bench"], "model": "m",
                   "candidates": [{"text": "A dog sits on a bench next to a giraffe.", "latency_ms": 1000, "probability": .5},
                                  {"text": "A dog on a bench.", "latency_ms": 1000, "probability": .6},
                                  {"text": "A dog sits on a bench.", "latency_ms": 1000, "probability": .6}]}]
    (gen / "pope_random.jsonl").write_text("".join(json.dumps(r) + "\n" for r in pope_rows))
    (gen / "chair.jsonl").write_text("".join(json.dumps(r) + "\n" for r in chair_rows))
    return gen


def test_process_and_report_end_to_end(tmp_path):
    gen, proc = _gen(tmp_path), tmp_path / "proc"
    cfg = load_config(tuned="__none__")
    for name in ("base_vlm", "full_toolkit"):
        process_file(gen / "pope_random.jsonl", name, proc, cfg, fake_verify)
    for name in ("base_vlm", "full_toolkit", "n_equals_1", "no_reliability_scoring", "no_attribute_binding"):
        process_file(gen / "chair.jsonl", name, proc, cfg, fake_verify)
    report = evaluate(proc)
    assert report["pope"]["base_vlm"]["random"]["accuracy"] == 2 / 3
    assert report["pope"]["full_toolkit"]["random"]["accuracy"] == 1.0  # giraffe 'yes' corrected to 'no'
    assert report["chair"]["base_vlm"]["CHAIR_S"] == 1.0
    assert report["chair"]["full_toolkit"]["CHAIR_S"] == 0.0
    assert report["latency"]["full_toolkit"]["ratio"] >= 1.0
    text = markdown(write_report(report, tmp_path / "r.json", {}))
    assert "## POPE" in text and "## CHAIR" in text


def test_tuning_finds_separating_threshold():
    rows = []
    for i in range(40):
        rows.append({"label": True, "pope": {"base_answer": True, "v": .6 + (i % 4) * .1}})
        rows.append({"label": False, "pope": {"base_answer": True, "v": .05}})
    tuned = tune_thresholds(rows, grounding_threshold=.3)
    assert tuned["f1"] == 1.0 and tuned["tau_lo"] >= .1 and tuned["tau_hi"] > tuned["tau_lo"]


def _pope_tune_rows(tmp_path):
    """Token confidence perfectly calibrated, visual score only partly: an unconstrained ECE search picks lambda_v = 0."""
    rows = []
    for i in range(60):
        label = i % 3 != 0
        rows.append({"label": label, "pope": {"base_answer": True, "v": .9 if i % 2 else .6, "p": 1.0 if label else 0.0}})
    path = tmp_path / "pope_tune.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows))
    return path


def test_tuning_keeps_config_reliability_weights_by_default(tmp_path):
    out = tmp_path / "tuned.yaml"
    tune_main(["--proc", str(_pope_tune_rows(tmp_path)), "--write", str(out)])
    import yaml
    tuned = yaml.safe_load(out.read_text())
    assert "reliability" not in tuned and "per_type" in tuned["decision"]
    assert tuned["tuning"]["weights"]["applied"] is False
    assert tuned["tuning"]["weights"]["unconstrained_search"]["lambda_verification"] == 0.0


def test_opt_in_weight_tuning_respects_the_visual_floor(tmp_path):
    out = tmp_path / "tuned.yaml"
    tune_main(["--proc", str(_pope_tune_rows(tmp_path)), "--write", str(out), "--tune-weights", "--min-visual-weight", ".5"])
    import yaml
    tuned = yaml.safe_load(out.read_text())
    assert tuned["tuning"]["weights"]["selected"]["lambda_verification"] >= .5
    assert tuned["reliability"]["lambda_verification"] >= tuned["reliability"]["lambda_probability"]
