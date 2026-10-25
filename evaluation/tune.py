"""Tune decision thresholds and reliability weights on the held-out POPE split.

    python -m evaluation.tune --proc results/proc/full_toolkit/pope_tune.jsonl --write results/tuned.yaml

* object (lo, hi): grid search maximising F1 of the final yes/no answers
  (tie-break: lower abstention), recomputed from stored v without re-verifying;
* reliability weights are NOT changed by default.  POPE answers are a single
  "yes"/"no" token from one candidate, so token confidence p_j is trivially well
  calibrated there and an unconstrained ECE search drives lambda_verification to 0,
  which would make R ignore visual evidence on captions (CHAIR).  The search is still
  run and recorded under ``tuning.weights`` for transparency.  ``--tune-weights``
  applies it, searching only lambda_verification >= ``--min-visual-weight``.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from core.config import load_config
from evaluation.evaluator import read_jsonl
from evaluation.metrics import binary_metrics, expected_calibration_error


def _answers(rows, lo, hi, grounding_threshold):
    finals, abstained = [], 0
    for r in rows:
        p = r["pope"]
        if not p["base_answer"] or p.get("v") is None:
            finals.append(bool(p["base_answer"])); continue
        v = p["v"]
        if v <= lo and v < grounding_threshold:
            finals.append(False)
        else:
            finals.append(True); abstained += lo < v < hi or (v <= lo and v >= grounding_threshold)
    return finals, abstained / len(rows) if rows else 0.0


def tune_thresholds(rows: list[dict], grounding_threshold: float, target_precision: float = .95) -> dict:
    """lo maximises F1 (answers depend only on lo); hi is the smallest value at which
    accepted claims (v >= hi) reach ``target_precision`` - the band between is flagged."""
    labels = [bool(r["label"]) for r in rows]
    best = None
    for lo in [x / 100 for x in range(10, 50, 5)]:
        finals, _ = _answers(rows, lo, 1.0, grounding_threshold)
        f1 = binary_metrics(labels, finals)["f1"]
        if best is None or round(f1, 6) > round(best[1], 6):
            best = (lo, f1)
    lo, f1 = best
    asserted = [(r["pope"]["v"], bool(r["label"])) for r in rows if r["pope"]["base_answer"] and r["pope"].get("v") is not None]
    hi = None
    for candidate in [x / 100 for x in range(int(lo * 100) + 5, 100, 5)]:
        accepted = [label for v, label in asserted if v >= candidate]
        if len(accepted) >= 10 and sum(accepted) / len(accepted) >= target_precision:
            hi = candidate; break
    hi = hi if hi is not None else max(.9, lo + .05)
    _, abstain = _answers(rows, lo, hi, grounding_threshold)
    return {"tau_lo": lo, "tau_hi": hi, "f1": f1, "abstention_rate": abstain, "accept_precision_target": target_precision}


def tune_weights(rows: list[dict], lo: float, grounding_threshold: float, min_visual: float = 0.0) -> dict:
    """ECE-minimising lambda_verification (share of lambda_verification + lambda_probability) on a 0.1 grid >= min_visual."""
    asserted = [r for r in rows if r["pope"]["base_answer"] and r["pope"].get("v") is not None and r["pope"].get("p") is not None]
    if len(asserted) < 30:
        return {}
    best = None
    for step in range(round(min_visual * 10), 11):
        l1 = step / 10
        probs, correct = [], []
        for r in asserted:
            p = r["pope"]
            probs.append(l1 * p["v"] + (1 - l1) * p["p"])
            final = not (p["v"] <= lo and p["v"] < grounding_threshold)
            correct.append(final == bool(r["label"]))
        ece, _ = expected_calibration_error(probs, correct)
        if best is None or ece < best[0]:
            best = (ece, {"lambda_verification": l1, "lambda_probability": round(1 - l1, 2), "ece": ece, "n": len(asserted)})
    return best[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--proc", required=True); parser.add_argument("--write", default="results/tuned.yaml")
    parser.add_argument("--tune-weights", action="store_true", help="also apply tuned reliability weights (default: keep config weights)")
    parser.add_argument("--min-visual-weight", type=float, default=.5, help="lowest lambda_verification share searched with --tune-weights")
    args = parser.parse_args(argv)
    rows = read_jsonl(args.proc)
    cfg = load_config(tuned="__none__")
    thresholds = tune_thresholds(rows, cfg.grounding_threshold)
    unconstrained = tune_weights(rows, thresholds["tau_lo"], cfg.grounding_threshold)
    weights = tune_weights(rows, thresholds["tau_lo"], cfg.grounding_threshold, args.min_visual_weight) if args.tune_weights else {}
    pair = {"tau_lo": thresholds["tau_lo"], "tau_hi": thresholds["tau_hi"]}
    weight_record = {"applied": bool(weights), "unconstrained_search": unconstrained}
    if weights:
        weight_record.update(min_visual_weight=args.min_visual_weight, selected=weights)
    tuned = {"decision": {"per_type": {"object": pair, "quantity": pair, "relation": pair}},
             "tuning": {"source": args.proc, "n": len(rows), "object_thresholds": thresholds, "weights": weight_record}}
    if weights:
        lambda_agreement = cfg.weights["agreement"]
        scale = 1 - lambda_agreement  # keep lambda_agreement's default share; split the rest as tuned
        tuned["reliability"] = {"lambda_verification": round(weights["lambda_verification"] * scale, 3),
                                "lambda_probability": round(weights["lambda_probability"] * scale, 3),
                                "lambda_agreement": lambda_agreement}
    Path(args.write).parent.mkdir(parents=True, exist_ok=True)
    Path(args.write).write_text(yaml.safe_dump(tuned, sort_keys=False))
    print(yaml.safe_dump(tuned, sort_keys=False))


if __name__ == "__main__":
    main()
