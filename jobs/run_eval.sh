#!/usr/bin/env bash
# Benchmark runner (Kaggle notebook, any Linux GPU box, or Git Bash on the Lenovo).
# Run from the repo root AFTER data prep + weight download (done once by the notebook):
#   bash jobs/run_eval.sh pope|chair|smoke
# Every stage is resumable; partial results are pushed to $RESULTS_REPO when set.
set -euo pipefail
BENCH=${1:?usage: run_eval.sh pope|chair|smoke}
PY=${PYTHON:-python}
export VLM_HARDWARE=${VLM_HARDWARE:-local}
REPO_ARGS=()
[ -n "${RESULTS_REPO:-}" ] && REPO_ARGS=(--repo "$RESULTS_REPO")

push() {  # push only this benchmark's files so parallel processes never clash
  [ -n "${RESULTS_REPO:-}" ] && $PY -m evaluation.hub_sync push --repo "$RESULTS_REPO" --patterns "$@" || true
}

case "$BENCH" in
  pope)
    # Held-out tuning split first, so tuned thresholds exist early (CHAIR waits for them).
    $PY -m evaluation.generate --input data/benchmarks/pope_tune.jsonl --out results/gen/pope_tune.jsonl \
      --n 1 --max-new-tokens 8 "${REPO_ARGS[@]}"
    $PY -m evaluation.process --gen results/gen/pope_tune.jsonl --ablation full_toolkit
    $PY -m evaluation.tune --proc results/proc/full_toolkit/pope_tune.jsonl --write results/tuned.yaml
    push "results/tuned.yaml" "results/gen/pope_tune.jsonl" "results/proc/full_toolkit/pope_tune.jsonl"
    for s in random popular adversarial; do
      $PY -m evaluation.generate --input data/benchmarks/pope_$s.jsonl --out results/gen/pope_$s.jsonl \
        --n 1 --max-new-tokens 8 --push-every 300 "${REPO_ARGS[@]}"
    done
    $PY -m evaluation.process --gen results/gen/pope_random.jsonl results/gen/pope_popular.jsonl results/gen/pope_adversarial.jsonl --all-ablations
    push "results/gen/pope_*" "results/proc/*/pope_*" "results/cache/verification_pope.jsonl"
    ;;
  chair)
    $PY -m evaluation.generate --input data/benchmarks/chair.jsonl --out results/gen/chair.jsonl \
      --n 3 --max-new-tokens 128 --push-every 50 "${REPO_ARGS[@]}"
    # CHAIR processing waits for tuned thresholds from the POPE process when it runs in parallel.
    for _ in $(seq 1 120); do [ -f results/tuned.yaml ] && break; sleep 30; done
    if [ ! -f results/tuned.yaml ]; then
      # Rows record "tuned": false and the report flags it; re-run process once tuned.yaml exists.
      echo "WARNING: results/tuned.yaml not found after 60 min (did the POPE process fail?); CHAIR uses DEFAULT thresholds" >&2
    fi
    $PY -m evaluation.process --gen results/gen/chair.jsonl --all-ablations
    push "results/gen/chair*" "results/proc/*/chair*" "results/cache/verification_chair.jsonl"
    ;;
  smoke)
    for s in random tune; do
      $PY -m evaluation.generate --input data/smoke/pope_$s.jsonl --out results/smoke/gen/pope_$s.jsonl --n 1 --max-new-tokens 8 --limit 5
    done
    $PY -m evaluation.generate --input data/smoke/chair.jsonl --out results/smoke/gen/chair.jsonl --n 3 --max-new-tokens 128 --limit 3
    $PY -m evaluation.process --gen results/smoke/gen/pope_random.jsonl results/smoke/gen/chair.jsonl --all-ablations --out-root results/smoke/proc
    $PY -m evaluation.run_benchmarks --proc results/smoke/proc --out results/smoke/benchmark_report.json --markdown results/smoke/RESULTS.md
    push "results/smoke/**"
    ;;
  *) echo "unknown benchmark: $BENCH" >&2; exit 2 ;;
esac
echo "run_eval.sh $BENCH finished"
