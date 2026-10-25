"""Generation stage: run the base VLM over a benchmark file (resumable).

    python -m evaluation.generate --input data/benchmarks/chair.jsonl --out results/gen/chair.jsonl \
        --n 3 --max-new-tokens 128 [--limit N] [--push-every 50 --repo ORG/NAME]

Candidate 1 is greedy (the uncorrected baseline); 2..n are sampled.  Samples
already present in ``--out`` are skipped, so a crashed run continues where it
stopped.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from core.config import raw_config


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if not row.get("error"):
                ids.add(row["sample_id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return ids


def read_jsonl(path: str | Path) -> list[dict]:
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def latest_rows(path: str | Path) -> list[dict]:
    """One row per sample_id (the last successful one), in first-seen order."""
    rows: dict[str, dict] = {}
    for row in read_jsonl(path):
        if row.get("error") or "sample_id" not in row:
            continue
        rows[row["sample_id"]] = row
    return list(rows.values())


def main(argv: list[str] | None = None) -> None:
    config = raw_config()
    gen, vlm = config.get("generation", {}), config.get("vlm", {})
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True); parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=vlm.get("hf_model", "llava-hf/llava-1.5-7b-hf"))
    parser.add_argument("--precision", default=vlm.get("hf_precision", "fp16"))
    parser.add_argument("--n", type=int, default=int(gen.get("num_candidates", 3)))
    parser.add_argument("--temperature", type=float, default=float(gen.get("temperature", .7)))
    parser.add_argument("--max-new-tokens", type=int, default=int(gen.get("max_new_tokens", 128)))
    parser.add_argument("--seed", type=int, default=int(gen.get("seed", 42)))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--push-every", type=int, default=0)
    parser.add_argument("--repo", default=os.getenv("RESULTS_REPO", ""))
    parser.add_argument("--hardware", default=os.getenv("VLM_HARDWARE", "local"))
    args = parser.parse_args(argv)

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(args.input)[:args.limit] if args.limit else read_jsonl(args.input)
    finished = done_ids(out)
    todo = [r for r in records if r["sample_id"] not in finished]
    print(f"{args.input}: {len(records)} samples, skipping {len(records) - len(todo)} done, {len(todo)} to generate", flush=True)
    if not todo:
        return

    import torch
    from tqdm import tqdm
    from models.hf_vlm import HFVLMEngine
    started = time.time()
    engine = HFVLMEngine(args.model, args.precision)
    meta = {"model": args.model, "precision": args.precision, "hardware": args.hardware,
            "generation": {"n": args.n, "temperature": args.temperature, "seed": args.seed, "max_new_tokens": args.max_new_tokens}}
    with out.open("a", encoding="utf-8") as stream:
        for count, record in enumerate(tqdm(todo, desc=out.stem, mininterval=10), start=1):
            try:
                rows = engine.generate_candidates(record["image_path"], record["query"], args.n, args.temperature,
                                                  args.max_new_tokens, args.seed)
                error = next((r["error"] for r in rows if r.get("error")), None)
                candidates = [{"text": r["response"], "probability": r["probability"], "num_tokens": r["num_tokens"],
                               "latency_ms": r["latency_ms"], "strategy": r["generation_strategy"]} for r in rows]
                stream.write(json.dumps({**record, **meta, "candidates": candidates, **({"error": error} if error else {})}) + "\n")
            except Exception as exc:  # log and continue; the sample is retried on the next run
                stream.write(json.dumps({"sample_id": record["sample_id"], "error": f"{type(exc).__name__}: {str(exc)[:300]}"}) + "\n")
            stream.flush()
            if count % 50 == 0 and torch.cuda.is_available():
                torch.cuda.empty_cache()
            if args.push_every and args.repo and count % args.push_every == 0:
                from evaluation.hub_sync import push
                push(args.repo, [out.as_posix()])
    if args.push_every and args.repo:
        from evaluation.hub_sync import push
        push(args.repo, [out.as_posix()])
    print(f"done in {time.time() - started:.0f}s -> {out}", flush=True)


if __name__ == "__main__":
    main()
