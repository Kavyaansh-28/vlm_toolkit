"""Metrics for explicitly labelled records; no synthetic scores are implied."""
from __future__ import annotations

MIN_CALIBRATION_SAMPLES = 30


def binary_metrics(labels: list[bool], predictions: list[bool]) -> dict:
    tp = sum(a and b for a, b in zip(labels, predictions)); fp = sum(not a and b for a, b in zip(labels, predictions))
    fn = sum(a and not b for a, b in zip(labels, predictions))
    precision = tp / (tp + fp) if tp + fp else 0.0; recall = tp / (tp + fn) if tp + fn else 0.0
    return {"accuracy": sum(a == b for a, b in zip(labels, predictions)) / len(labels) if labels else 0.0,
            "precision": precision, "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}


_binary_metrics = binary_metrics


def expected_calibration_error(probabilities: list[float], labels: list[bool], bins: int = 10) -> tuple[float, list[dict]]:
    diagram = []
    for index in range(bins):
        subset = [(p, y) for p, y in zip(probabilities, labels) if min(bins - 1, int(p * bins)) == index]
        if subset:
            diagram.append({"lower": index / bins, "upper": (index + 1) / bins, "count": len(subset),
                            "mean_confidence": sum(p for p, _ in subset) / len(subset),
                            "accuracy": sum(int(y) for _, y in subset) / len(subset)})
    ece = sum(b["count"] / len(labels) * abs(b["mean_confidence"] - b["accuracy"]) for b in diagram) if labels else 0.0
    return ece, diagram


def classification_metrics(records: list[dict]) -> dict:
    """Labelled binary metrics, Brier score and binned calibration.

    Records need `expected_reliable` and `reliability` in [0, 1]. Calibration
    needs at least 30 records to avoid presenting tiny-sample diagrams. Optional
    `error_type`/`predicted_error_type` fields produce per-error-type detection stats.
    """
    labelled = [r for r in records if "expected_reliable" in r and "reliability" in r]
    if not labelled:
        return {"available": False, "message": "Calibration unavailable: insufficient evaluation samples. Supply labelled records before reporting metrics.", "calibration_available": False}
    y = [bool(r["expected_reliable"]) for r in labelled]
    p = [max(0.0, min(1.0, float(r["reliability"]))) for r in labelled]
    result = {"available": True, **binary_metrics(y, [x >= .5 for x in p]),
              "brier": sum((x - int(t)) ** 2 for x, t in zip(p, y)) / len(y), "sample_count": len(y)}
    if len(y) < MIN_CALIBRATION_SAMPLES:
        result.update({"calibration_available": False, "ece": None, "reliability_diagram": [],
                       "calibration_message": f"Calibration unavailable: insufficient evaluation samples (need at least {MIN_CALIBRATION_SAMPLES} labelled rows)."})
    else:
        ece, diagram = expected_calibration_error(p, y)
        result.update({"calibration_available": True, "ece": ece, "reliability_diagram": diagram})
    error_types = sorted({r.get("error_type") for r in labelled if r.get("error_type")})
    if error_types:
        result["error_detection"] = {error: binary_metrics([r.get("error_type") == error for r in labelled],
                                                           [r.get("predicted_error_type") == error for r in labelled]) for error in error_types}
    decisions = [r.get("decision") for r in labelled if r.get("decision")]
    if decisions:
        result["abstention_rate"] = sum(x == "ABSTAIN" for x in decisions) / len(decisions)
    return result
