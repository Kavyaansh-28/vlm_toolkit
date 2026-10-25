"""Dataset-agnostic, runnable evaluation harnesses.

Adapters consume prepared JSONL records rather than downloading benchmark data
silently. They report only labels provided by the dataset/run and never embed
paper targets as results.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from evaluation.metrics import classification_metrics


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def pope(records: list[dict]) -> dict:
    """POPE accuracy/precision/recall/F1/yes-ratio by random/popular/adversarial split.

    Each record needs ``split``, boolean ``label`` and boolean ``prediction``.
    """
    out = {"benchmark": "POPE", "status": "EVALUATED" if records else "NOT RUN", "splits": {}}
    for split in ("random", "popular", "adversarial"):
        rows = [r for r in records if r.get("split") == split]
        if not rows:
            out["splits"][split] = {"status": "NOT RUN", "sample_count": 0}; continue
        labels, predictions = [bool(r["label"]) for r in rows], [bool(r["prediction"]) for r in rows]
        result = classification_metrics([{"expected_reliable": a, "reliability": float(b)} for a,b in zip(labels,predictions)])
        result["yes_ratio"] = sum(predictions) / len(predictions); result["status"] = "EVALUATED"
        out["splits"][split] = result
    return out


def chair(records: list[dict]) -> dict:
    """CHAIR from caption object sets: ground_truth_objects, mentioned_objects."""
    if not records: return {"benchmark": "CHAIR", "status": "NOT RUN"}
    sentences = instances = hallucinated = mentioned = truth = matched = 0
    for row in records:
        gt, pred = set(row.get("ground_truth_objects", [])), set(row.get("mentioned_objects", []))
        bad = pred - gt; sentences += 1; instances += bool(bad); hallucinated += len(bad); mentioned += len(pred); truth += len(gt); matched += len(pred & gt)
    return {"benchmark": "CHAIR", "status": "EVALUATED", "sample_count": sentences,
            "CHAIR_S": instances / sentences if sentences else 0, "CHAIR_I": hallucinated / mentioned if mentioned else 0,
            "object_recall": matched / truth if truth else 0}


def winoground(records: list[dict]) -> dict:
    """Winoground labels need text_correct and image_correct per group."""
    if not records: return {"benchmark": "Winoground", "status": "NOT RUN"}
    text = sum(bool(r.get("text_correct")) for r in records) / len(records)
    image = sum(bool(r.get("image_correct")) for r in records) / len(records)
    group = sum(bool(r.get("text_correct")) and bool(r.get("image_correct")) for r in records) / len(records)
    return {"benchmark": "Winoground", "status": "EVALUATED", "sample_count": len(records), "text_score": text, "image_score": image, "group_score": group}


def sugarcrepe(records: list[dict]) -> dict:
    if not records: return {"benchmark": "SugarCrepe", "status": "NOT RUN"}
    categories = {}
    for category in ("replace", "swap", "add"):
        rows = [r for r in records if r.get("category") == category]
        categories[category] = {"status": "EVALUATED", "accuracy": sum(bool(x.get("correct")) for x in rows)/len(rows), "sample_count": len(rows)} if rows else {"status":"NOT RUN", "sample_count":0}
    return {"benchmark": "SugarCrepe", "status": "EVALUATED", "categories": categories}


def run_all(dataset_dir: str | Path) -> dict:
    root = Path(dataset_dir)
    loaders = {"pope": pope, "chair": chair, "winoground": winoground, "sugarcrepe": sugarcrepe}
    return {name: handler(read_jsonl(root / f"{name}.jsonl")) if (root / f"{name}.jsonl").exists() else handler([]) for name, handler in loaders.items()}
