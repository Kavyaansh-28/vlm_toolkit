"""Benchmark scoring over processed rows (results/proc/<ablation>/<file>.jsonl).

Reports only what the runs produced; nothing here embeds a paper target as a result.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from core.config import load_config
from evaluation.chair import chair
from evaluation.metrics import binary_metrics, classification_metrics

SPLITS = ("random", "popular", "adversarial")


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def pope(rows: list[dict]) -> dict:
    """Accuracy / precision / recall / F1 / yes-ratio (positive class = yes) + abstention rate."""
    if not rows:
        return {"status": "NOT RUN", "sample_count": 0}
    labels = [bool(r["label"]) for r in rows]
    answers = [bool(r["pope"]["final_answer"]) for r in rows]
    result = binary_metrics(labels, answers)
    result.update(status="EVALUATED", sample_count=len(rows), yes_ratio=sum(answers) / len(answers),
                  abstention_rate=sum(bool(r["pope"].get("abstained")) for r in rows) / len(rows),
                  corrected_yes_to_no=sum(r["pope"]["base_answer"] and not r["pope"]["final_answer"] for r in rows))
    return result


def latency(rows: list[dict]) -> dict:
    timed = [r["latency_ms"] for r in rows if r.get("latency_ms", {}).get("generation_base")]
    if not timed:
        return {"available": False}
    base, total = mean(t["generation_base"] for t in timed), mean(t["total"] for t in timed)
    return {"available": True, "mean_base_ms": round(base), "mean_total_ms": round(total),
            "ratio": round(total / base, 2) if base else None, "measured_on": timed[0].get("measured_on", "unknown")}


def pope_calibration(rows: list[dict]) -> dict:
    """ECE/Brier of R_j against 'final answer correct' on asserted (yes) claims."""
    records = [{"expected_reliable": bool(r["pope"]["final_answer"]) == bool(r["label"]), "reliability": r["pope"]["reliability"]}
               for r in rows if r["pope"].get("reliability") is not None]
    return classification_metrics(records)


def evaluate(proc_root: str | Path) -> dict:
    root = Path(proc_root)
    report: dict = {"pope": {}, "chair": {}, "latency": {}, "calibration": {}}
    for ablation_dir in sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []:
        name = ablation_dir.name
        for split in SPLITS:
            path = ablation_dir / f"pope_{split}.jsonl"
            if path.exists():
                rows = read_jsonl(path)
                report["pope"].setdefault(name, {})[split] = pope(rows)
                if name == "full_toolkit":
                    report["calibration"][f"pope_{split}"] = pope_calibration(rows)
        chair_path = ablation_dir / "chair.jsonl"
        if chair_path.exists():
            rows = read_jsonl(chair_path)
            report["chair"][name] = chair(rows)
            report["latency"][name] = latency(rows)
    report["meta"] = _meta(root)
    return report


def _meta(root: Path) -> dict:
    cfg = load_config()
    sample = next(iter(sorted(root.glob("*/*.jsonl"))), None) if root.exists() else None
    first = read_jsonl(sample)[0] if sample and sample.stat().st_size else {}
    return {"model": first.get("model"), "precision": first.get("precision"),
            "hardware": (first.get("latency_ms") or {}).get("measured_on"),
            "thresholds": {k: list(v) for k, v in cfg.thresholds.items()}, "weights": cfg.weights,
            "rerank_threshold": cfg.rerank_threshold, "tuned": (Path("results") / "tuned.yaml").exists()}
