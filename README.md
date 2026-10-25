# VLM Reliability Toolkit

A training-free, model-agnostic, inference-time reliability layer for Vision-Language Models. It implements *VLM Reliability Toolkit: Unified Inference-Time Hallucination Detection and Attribute-Binding Correction for Vision-Language Models* (`VLM_Reliability_Toolkit_IEEE_Paper.pdf`).

The toolkit generates n candidate responses and decomposes each into atomic claims. It verifies existence claims with Grounding DINO and attribute bindings with CLIP on the object's own crop. It then scores every candidate (Eq. 3) and applies the per-claim **accept / correct / re-rank / abstain** policy. Verified content is never modified.

## Status

| Paper component | Where | Status |
|---|---|---|
| VLM Execution Engine: API VLMs + local HF VLMs (LLaVA, LLaVA-OneVision, BLIP-2) | `vlm.py`, `vlm_engine.py`, `models/hf_vlm.py` | Done |
| n-best candidates: greedy candidate 1 (baseline) + sampled 2..n; p_j = exp(mean token log-prob) | `models/hf_vlm.py` | Done (`hf-local`); API models: repeated calls, p_j only from OpenAI log-probs |
| Claim extraction: existence, colour/material binding, counts, spatial relations | `claims/extractor.py`, `claims/vocab.py` | Done. Rule-based over the 80 COCO classes + CHAIR synonyms |
| Eq. 1 existence: s_obj = max d_b (Grounding DINO) | `verification/object_verifier.py` | Done |
| Eq. 2 binding: s_attr = max d_b·P(a\|crop_b) (CLIP on the grounded crop), colour + material | `verification/attribute_verifier.py` | Done |
| Counts (NMS) and spatial relations (box geometry) | `verification/service.py` | Done |
| Eq. 3 reliability: R = λ₁·mean(v) + λ₂·p + λ₃·A, unavailable terms redistributed | `reliability/engine.py` | Done |
| Decision policy: per-claim accept/correct/abstain, paper re-rank rule | `core/policy.py`, `core/pipeline.py` | Done |
| Correction: replace / swap mis-bound attributes, delete hallucinated objects | `correction/engine.py` | Done |
| Audit log (image hash, candidates, claim scores, action taken) + human review | `database/db.py`, `api/server.py` | Done |
| FastAPI service + Next.js dashboard | `api/server.py`, `frontend/` | Done |
| POPE + CHAIR harness, ablations, latency ratio, calibration, held-out tuning | `evaluation/` | Done; **results come from the Kaggle run** |
| Winoground, SugarCrepe | — | Not in this release |

## Quick start

### 1. Python environment (Windows PowerShell)
```powershell
py -3.12 -m venv .venv            # 3.11 or 3.12 recommended
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install torch torchvision      # CUDA build: add --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
copy .env.example .env             # add GEMINI_API_KEY (free tier) for live demos
python -m pytest -q
```

### macOS (Apple Silicon)
```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip && pip install torch torchvision && pip install -r requirements.txt
export PYTORCH_ENABLE_MPS_FALLBACK=1      # some Grounding DINO ops fall back to CPU
cp .env.example .env && python -m pytest -q
```

### 2. Paper Table IV example (no models, no API key)
```bash
python demo_paper_example.py
```
Expected output: *"A person in a red shirt and blue jeans stands on the beach."* The shirt and jeans colours are **swapped** and the surfboard is **deleted**. This is an evidence fixture that runs the real pipeline on fixed verifier outputs.

### 3. Dashboard
```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1     # Windows
./dev-frontend.sh                                            # macOS / Linux
```
- Backend: `http://127.0.0.1:8010/health` (FastAPI: `uvicorn api.server:app --port 8010`)
- Dashboard: `http://127.0.0.1:3000`. The pages are Analyze, Claims, Evidence, Candidates, **Review** (flagged-claim annotation), **Evaluation** (POPE/CHAIR tables) and Experiments.
- The first analysis downloads Grounding DINO-tiny and CLIP (~1.3 GB). Then set `verification.local_files_only: true`.
- Use the **Controlled candidate override** box (candidates separated by `|||`) to demo without any API key.

If `pnpm install` fails with a 401 from a private registry, install from the public one: `corepack pnpm install --registry=https://registry.npmjs.org/`.

## Configuration: `config/config.yaml`

| Key | Meaning |
|---|---|
| `vlm.hf_model`, `vlm.hf_precision` | Local model for `hf-local` and benchmarks (`fp16` or `4bit`) |
| `generation.*` | n candidates, temperature for samples 2..n, max new tokens, seed |
| `reliability.lambda_*`, `rerank_threshold` | Eq. 3 weights; R threshold for re-rank / "no reliable candidate" |
| `decision.per_type.<type>.tau_lo/tau_hi` | Per-claim thresholds (object, attribute, quantity, relation) |
| `verification.*` | Detector/probe models, support threshold, detection floor, device, cache |

`results/tuned.yaml`, written by `evaluation/tune.py` on the held-out split, overrides these values automatically.

## Benchmarks (POPE + CHAIR) on Kaggle's free GPU

1. Kaggle notebook: **GPU T4 x2**, Internet **On**. Add the secrets `HF_TOKEN` (and `GH_TOKEN` if the repo is private). The account must be phone-verified.
2. Upload `kaggle/run_benchmarks.ipynb`. Set `BENCHES = ["smoke"]` and run it interactively once as a check.
3. Set `BENCHES = ["pope", "chair"]`, then **Save Version → Save & Run All (Commit)**. POPE runs on GPU 0 and CHAIR on GPU 1, taking about 4 h. Results are pushed to the HF dataset repo every 50–300 samples, and re-running resumes.
4. Download the results and build the report on any laptop:
```bash
hf download vlm-reliability-pccoe/vlm-results --repo-type dataset --local-dir . --include "results/*"
python -m evaluation.run_benchmarks --proc results/proc --out results/benchmark_report.json --markdown results/RESULTS.md
```
5. To change thresholds or ablations afterwards without a GPU, use the cached verifier outputs:
```bash
python -m evaluation.tune --proc results/proc/full_toolkit/pope_tune.jsonl --write results/tuned.yaml
python -m evaluation.process --gen results/gen/pope_random.jsonl results/gen/pope_popular.jsonl results/gen/pope_adversarial.jsonl results/gen/chair.jsonl --all-ablations --cache-only
```

**Pipeline stages** (each is a CLI and resumable):

| Stage | Command |
|---|---|
| Data | `python -m evaluation.prepare_data --pope-images 450 --chair-images 500 --tune-images 50` |
| Generate | `python -m evaluation.generate --input data/benchmarks/chair.jsonl --out results/gen/chair.jsonl --n 3` |
| Process | `python -m evaluation.process --gen results/gen/chair.jsonl --all-ablations` |
| Tune | `python -m evaluation.tune --proc results/proc/full_toolkit/pope_tune.jsonl` |
| Report | `python -m evaluation.run_benchmarks` |

**Protocol notes for the paper:**
- **POPE:** 450 COCO images × 3 splits. The other 50 of POPE's 500 images form the held-out tuning split and are never reported.
- **CHAIR:** 500 COCO val2014 images, with ground truth from instance annotations and the CHAIR synonym list.
- **Baseline:** candidate 1, i.e. greedy decoding by the same model.
- **Ablations:** `base_vlm`, `full_toolkit`, `no_attribute_binding`, `no_reliability_scoring`, `n_equals_1`.
- **Scope of these benchmarks:** POPE and CHAIR measure object hallucination only, so attribute-binding correction is not measured by them.

## Repository map
```text
api/server.py          FastAPI service (analyze, history, review queue, benchmarks)
core/                  schemas, config loading, pipeline, decision policy
claims/                COCO vocabulary + CHAIR synonyms, claim extractor, claim graph
verification/          Grounding DINO, CLIP region probe, verification service, on-disk cache
reliability/engine.py  Eq. 3 and candidate agreement
correction/engine.py   evidence-driven replace / swap / delete
models/hf_vlm.py       local HF VLM engine (n-best, token probabilities)
vlm.py, vlm_engine.py  API providers and engine selection
evaluation/            prepare_data, generate, process, tune, chair, metrics, reports, ablations
jobs/run_eval.sh       benchmark runner used by the Kaggle notebook
kaggle/                Kaggle notebook (+ .py source)
database/db.py         SQLite audit log and annotations
frontend/              Next.js dashboard
demo/DEMO.md           5-minute demo script
tests/                 unit, pipeline, API and evaluation tests (no GPU needed)
```

## Limitations
- Correction is bounded by the verifier: small, occluded or out-of-vocabulary objects can be missed, and Grounding DINO-tiny sometimes produces moderate-confidence false positives.
- Claim-extraction errors propagate downstream.
- Colour is sensitive to lighting.
- Aggressive deletion can trade recall for precision, so object recall is reported with CHAIR.
- Thresholds must be calibrated on held-out data.
- Post-generation correction adds latency (the ratio is reported).
- Reasoning errors, toxicity and adversarial robustness are out of scope.
