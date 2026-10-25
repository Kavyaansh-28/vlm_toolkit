"""Persist reproducible evaluation reports without claiming unrun metrics."""
from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

CHAIR_ORDER = ("base_vlm", "full_toolkit", "n_equals_1", "no_reliability_scoring", "no_attribute_binding")


def write_report(result: dict, path: str | Path, configuration: dict, seed: int = 42) -> dict:
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "seed": seed,
               "configuration": configuration, "environment": {"python": sys.version, "platform": platform.platform()},
               "results": result}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2))
    return payload


def _settings_lines(meta: dict) -> list[str]:
    """Settings recorded in the processed rows; mixed or untuned runs are called out."""
    if meta.get("mixed_settings"):
        lines = ["> **Warning:** processed files were produced with different settings; compare rows with care.", ""]
        for item in meta["mixed_settings"]:
            c = item["config"] or {}
            lines.append(f"- {', '.join(item['files'])}: thresholds {c.get('thresholds')} · λ {c.get('weights')} · tuned {c.get('tuned')}")
        return lines
    if meta.get("tuned") is None:
        return ["> **Warning:** processed rows carry no recorded settings; reprocess them to report thresholds."]
    lines = [f"Claim thresholds (lo, hi): {meta.get('thresholds')} · λ = {meta.get('weights')} · rerank threshold {meta.get('rerank_threshold')}"]
    if not meta.get("tuned"):
        lines += ["", "> **Warning:** default thresholds were used (no tuned.yaml when these rows were processed)."]
    return lines


def _pct(value) -> str:
    return "—" if value is None else f"{100 * value:.1f}"


def markdown(payload: dict) -> str:
    results, meta = payload["results"], payload["results"].get("meta", {})
    lines = ["# Benchmark results", "",
             f"Generated {payload['timestamp'][:19]} UTC · seed {payload['seed']} · model `{meta.get('model')}` "
             f"({meta.get('precision')}) · hardware `{meta.get('hardware')}` · thresholds tuned on held-out split: {meta.get('tuned')}", "",
             *_settings_lines(meta), "",
             "> POPE uses 450 COCO images per split (50 of POPE's 500 images are held out for tuning); "
             "the paper's 500-image target refers to the full release. POPE/CHAIR measure object hallucination only; "
             "attribute binding is not measured by these benchmarks.", ""]
    if results.get("pope"):
        lines += ["## POPE", "", "| Variant | Split | N | Acc | Prec | Rec | F1 | Yes % | Abstain % |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name in ("base_vlm", "full_toolkit", *sorted(set(results["pope"]) - {"base_vlm", "full_toolkit"})):
            for split, m in results["pope"].get(name, {}).items():
                if m.get("status") != "EVALUATED": continue
                lines.append(f"| {name} | {split} | {m['sample_count']} | {_pct(m['accuracy'])} | {_pct(m['precision'])} | {_pct(m['recall'])} | "
                             f"{_pct(m['f1'])} | {_pct(m['yes_ratio'])} | {_pct(m['abstention_rate'])} |")
        lines.append("")
    if results.get("chair"):
        lines += ["## CHAIR", "", "| Variant | N | CHAIR_S ↓ | CHAIR_I ↓ | Recall ↑ | Avg words | Latency × | Total ms |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for name in [n for n in CHAIR_ORDER if n in results["chair"]] + sorted(set(results["chair"]) - set(CHAIR_ORDER)):
            m, lat = results["chair"][name], results.get("latency", {}).get(name, {})
            lines.append(f"| {name} | {m['sample_count']} | {_pct(m['CHAIR_S'])} | {_pct(m['CHAIR_I'])} | {_pct(m['object_recall'])} | "
                         f"{m['avg_length']:.1f} | {lat.get('ratio', '—')} | {lat.get('mean_total_ms', '—')} |")
        lines.append("")
    if results.get("calibration"):
        lines += ["## Calibration of R (POPE, asserted claims)", "", "| Split | N | ECE | Brier |", "|---|---:|---:|---:|"]
        for split, m in results["calibration"].items():
            if m.get("available"):
                ece = "—" if m.get("ece") is None else f"{m['ece']:.3f}"
                lines.append(f"| {split} | {m['sample_count']} | {ece} | {m['brier']:.3f} |")
        lines.append("")
    if not results.get("pope") and not results.get("chair"):
        lines.append("No processed benchmark rows found: status NOT RUN.")
    return "\n".join(lines) + "\n"
