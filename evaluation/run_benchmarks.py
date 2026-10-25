"""CLI: python -m evaluation.run_benchmarks --data data/benchmarks --out results/report.json"""
from __future__ import annotations
import argparse
from evaluation.evaluator import run_all
from evaluation.reports import write_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--data", required=True); parser.add_argument("--out", default="results/benchmark_report.json"); parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(); result = run_all(args.data); write_report(result, args.out, {"data_dir": args.data}, args.seed); print(args.out)
