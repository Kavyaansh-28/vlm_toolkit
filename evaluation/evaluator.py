"""Benchmark scoring over processed rows (results/proc/<ablation>/<file>.jsonl).

Reports only what the runs produced; nothing here embeds a paper target as a result.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

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
    """Describe the run from the settings recorded in the processed rows themselves,
    never from the config at report time (it may have changed since processing)."""
    files = sorted(p for p in root.glob("*/*.jsonl") if not p.name.endswith(".partial.jsonl")) if root.exists() else []
    first: dict = {}
    configs: dict[str, list[str]] = {}
    for path in files:
        for row in read_jsonl(path):
            first = first or row
            key = json.dumps(row.get("config"), sort_keys=True)
            configs.setdefault(key, [])
            label = f"{path.parent.name}/{path.stem}"
            if label not in configs[key]:
                configs[key].append(label)
    settings = [json.loads(key) for key in configs]
    meta = {"model": first.get("model"), "precision": first.get("precision"),
            "hardware": (first.get("latency_ms") or {}).get("measured_on"), "consistent": len(settings) == 1}
    if len(settings) == 1 and settings[0]:
        meta.update(settings[0])
    elif len(settings) > 1:
        meta["mixed_settings"] = [{"config": json.loads(key), "files": labels} for key, labels in configs.items()]
        meta["tuned"] = all((s or {}).get("tuned") for s in settings)
    else:
        meta["tuned"] = None  # rows predate provenance recording
    return meta
