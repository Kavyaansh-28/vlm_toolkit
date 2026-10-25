"""Process stage: verify, score, decide and correct generated outputs (resumable).

Every row records the settings it was produced with (``config``), which the report uses.

    python -m evaluation.process --gen results/gen/chair.jsonl --ablation full_toolkit
    python -m evaluation.process --gen results/gen/pope_random.jsonl --all-ablations
    python -m evaluation.process --gen ... --all-ablations --cache-only   # laptop: no models, cache only

Writes results/proc/<ablation>/<gen file name>.  Verifier outputs are cached in
results/cache/verification_<benchmark>.jsonl, so reprocessing with tuned
thresholds or other ablations needs no GPU.  Verification latency is the stored
compute time of each verifier output, so it is identical across ablations and
reprocessing and reflects the hardware that computed it.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from time import perf_counter

from claims.vocab import to_class
from core.config import PipelineConfig, load_config
from core.pipeline import process_candidates
from core.policy import claim_action
from core.schemas import Candidate, Claim
from evaluation.ablations import ABLATIONS, ablation_config
from evaluation.generate import latest_rows
from reliability.engine import score
from verification.cache import cost_ms, reset_cost

POPE_ABLATIONS = ("base_vlm", "full_toolkit")


def parse_yes_no(text: str) -> bool:
    """Standard POPE answer parsing: 'no'/'not' anywhere in the first sentence -> no."""
    first = re.split(r"[.\n]", text.strip().lower(), maxsplit=1)[0]
    words = set(re.findall(r"[a-z']+", first))
    return not bool(words & {"no", "not", "isn't", "aren't"})


def _verify(image_path, claims, attribute=True):
    from verification.service import verify
    return verify(image_path, claims, attribute=attribute)


def _timed(fn, image_path, claims):
    """Verification cost from the verifier cache accounting (true compute time, also on
    cache hits; model loading excluded). Falls back to wall clock for uncached fakes."""
    reset_cost()
    started = perf_counter()
    result = fn(image_path, claims)
    wall = (perf_counter() - started) * 1000
    return round(cost_ms() or wall), result


def process_pope(record: dict, ablation: str, cfg: PipelineConfig, verify_fn=_verify) -> dict:
    cand = record["candidates"][0]
    base = parse_yes_no(cand["text"])
    row = {"base_answer": base, "final_answer": base, "v": None, "p": cand.get("probability"),
           "abstained": False, "claim_action": "NO_CLAIM"}
    verification_ms = 0
    if base and ablation != "base_vlm":
        claim = Claim(f"pope-{record['sample_id']}", "object", to_class(record["object"], include_extra=False) or record["object"],
                      surface=record["object"])
        verification_ms, evidence = _timed(verify_fn, record["image_path"], [claim])
        ev = evidence[0] if evidence else None
        candidate = Candidate("candidate-1", cand["text"], record.get("model", ""), claims=[claim], evidence=evidence,
                              probability=cand.get("probability"), probability_available=cand.get("probability") is not None)
        score(candidate, cfg)
        v = candidate.claim_values.get(claim.id)
        action = claim_action(v, ev, claim, cfg)
        row.update(v=v, reliability=candidate.reliability, claim_action=action, abstained=action == "ABSTAIN",
                   final_answer=False if action == "CORRECT" else True,
                   evidence_status=ev.status if ev else None)
    decision = row["claim_action"] if row["claim_action"] in {"CORRECT", "ABSTAIN"} else "ACCEPT"
    return {"pope": row, "decision": decision, "verification_ms": verification_ms}


def process_chair(record: dict, cfg: PipelineConfig, verify_fn=_verify) -> dict:
    rows = [{"response": c["text"], "probability": c.get("probability"), "probability_available": c.get("probability") is not None,
             "num_tokens": c.get("num_tokens"), "latency_ms": c.get("latency_ms"), "generation_strategy": c.get("strategy", ""),
             "model": record.get("model", "")} for c in record["candidates"]]
    verification_ms, candidates = _timed(lambda image, _: process_candidates(image, rows, cfg, verify_fn=verify_fn), record["image_path"], None)
    chosen = candidates[0]
    return {"final_text": chosen.corrected_text, "decision": chosen.decision, "decision_reason": chosen.decision_reason,
            "selected_candidate": int(chosen.id.rsplit("-", 1)[-1]) - 1, "reliability": chosen.reliability,
            "claim_actions": chosen.claim_actions, "action_details": chosen.action_details,
            "claim_values": chosen.claim_values, "verification_ms": verification_ms}


def _process_record(record: dict, ablation: str, cfg: PipelineConfig, verify_fn, provenance: dict) -> dict:
    candidates = record["candidates"]
    used = candidates[:cfg.candidate_count]
    if record["benchmark"] == "pope":
        result = process_pope(record, ablation, cfg, verify_fn)
    else:
        result = process_chair(record, cfg, verify_fn)
    latency = {"generation_base": candidates[0].get("latency_ms") or 0,
               "generation_all": sum(c.get("latency_ms") or 0 for c in used),
               "verification": result.pop("verification_ms"), "measured_on": record.get("hardware", "local")}
    latency["total"] = latency["generation_all"] + latency["verification"]
    keep = {k: record[k] for k in ("sample_id", "benchmark", "split", "image_id", "object", "label", "gt_objects") if k in record}
    return {**keep, "ablation": ablation, "model": record.get("model"), "precision": record.get("precision"),
            "base_text": candidates[0]["text"], **result,
            **({"final_text": candidates[0]["text"]} if record["benchmark"] == "pope" else {}),
            "latency_ms": latency, "config": provenance}


def process_file(gen_path: Path, ablation: str, out_root: Path, base_cfg: PipelineConfig, verify_fn=_verify) -> Path:
    """Process every generated row; resumable.

    Rows are appended to ``<name>.partial.jsonl`` as they finish and the file
    replaces the output at the end.  A rerun reuses finished rows (from either
    file) only when they were produced with the same settings, so an
    interrupted run continues, while changed thresholds or weights recompute.
    """
    out = out_root / ablation / gen_path.name
    partial = out.with_name(out.stem + ".partial.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    cfg = ablation_config(ablation, base_cfg)
    provenance = cfg.provenance()
    reusable = {}
    for path in (out, partial):
        if path.exists():
            reusable.update({row["sample_id"]: row for row in latest_rows(path) if row.get("config") == provenance})
    records = latest_rows(gen_path)
    reused = 0
    with partial.open("w", encoding="utf-8") as stream:
        for record in records:
            row = reusable.get(record["sample_id"])
            if row is None:
                row = _process_record(record, ablation, cfg, verify_fn, provenance)
            else:
                reused += 1
            stream.write(json.dumps(row) + "\n")
            stream.flush()
    partial.replace(out)
    print(f"{ablation:>24}: {len(records)} rows ({reused} reused) -> {out}", flush=True)
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gen", required=True, nargs="+")
    parser.add_argument("--ablation", default="full_toolkit", choices=list(ABLATIONS))
    parser.add_argument("--all-ablations", action="store_true")
    parser.add_argument("--out-root", default="results/proc")
    parser.add_argument("--cache-only", action="store_true", help="never load models; fail on a cache miss")
    parser.add_argument("--fake-verifier", action="store_true", help="CI smoke: deterministic fake evidence")
    args = parser.parse_args(argv)

    from verification import service
    base_cfg = load_config()
    verify_fn = _verify
    if args.fake_verifier:
        from evaluation.fake import fake_verify as verify_fn
    for gen in map(Path, args.gen):
        records = latest_rows(gen)
        if not records:
            print(f"{gen}: no generated rows yet"); continue
        benchmark = records[0]["benchmark"]
        service.configure(cache_name=f"verification_{benchmark}", cache_only=args.cache_only)
        names = (POPE_ABLATIONS if benchmark == "pope" else tuple(ABLATIONS)) if args.all_ablations else (args.ablation,)
        for name in names:
            process_file(gen, name, Path(args.out_root), base_cfg, verify_fn)


if __name__ == "__main__":
    main()
