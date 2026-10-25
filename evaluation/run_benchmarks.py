"""Build the benchmark report from processed rows.

    python -m evaluation.run_benchmarks --proc results/proc --out results/benchmark_report.json --markdown results/RESULTS.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.evaluator import evaluate
from evaluation.reports import markdown, write_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--proc", default="results/proc")
    parser.add_argument("--out", default="results/benchmark_report.json")
    parser.add_argument("--markdown", default="results/RESULTS.md")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = evaluate(args.proc)
    payload = write_report(result, args.out, {"proc_dir": args.proc}, args.seed)
    Path(args.markdown).write_text(markdown(payload), encoding="utf-8")
    print(f"{args.out}\n{args.markdown}")
