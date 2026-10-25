# VLM Reliability Toolkit

A training-free, model-agnostic reliability layer for Vision-Language Models (VLMs). It does **not** retrain or modify the base VLM. Instead, it generates one or more candidate responses, decomposes them into visual claims, independently verifies claims against the image, and returns an evidence-backed `ACCEPT`, `CORRECT`, `RERANK`, or `ABSTAIN` decision.

This repository implements the methodology in *VLM Reliability Toolkit: Unified Inference-Time Hallucination Detection and Attribute-Binding Correction for Vision-Language Models*.

## Project status - read this first

| Area | Status | What this means |
|---|---|---|
| Candidate generation | Implemented | Uses repeated controlled provider calls, explicitly **not** native n-best logits. |
| Claim extraction | Implemented, limited coverage | Rule-based extraction currently covers a curated object vocabulary, colors, simple counts, and simple spatial relations. |
| Object verification | Implemented | Grounding DINO provides open-vocabulary boxes and detector scores. YOLO is not used. |
| Attribute-binding verification | Implemented for color | CLIP scores color prompts on the **grounded object crop**, never on the full image. |
| Reliability / decisions / correction | Implemented and unit tested | Uses the paper's score, agreement, available token confidence, and conservative correction policy. |
| Dashboard and audit log | Implemented | Next.js dashboard plus SQLite records and JSON export. |
| Benchmark runners / ablations / calibration | Implemented | Require prepared labelled benchmark JSONL data. |
| Real benchmark results | **NOT RUN** | No POPE, CHAIR, Winoground, or SugarCrepe score is claimed by this repository. |
| Live end-to-end model run | Environment dependent | Requires a valid VLM API key plus downloaded Grounding DINO and CLIP model weights. |

## Paper-to-code compliance

| Paper requirement | Implementation | Notes |
|---|---|---|
| Interchangeable black-box VLM | `vlm_engine.py`, `vlm.py` | OpenAI, Groq-compatible, Gemini, and OpenAI-compatible Llama endpoints are supported. |
| Multiple candidates | `ProviderVLMEngine.generate_candidates()` | Repeated controlled generation is recorded in the audit log. |
| Atomic existence and binding claims | `claims/extractor.py`, `core/schemas.py` | Each claim has a stable ID, type, normalized subject, source text, value, and relation target where applicable. |
| Open-vocabulary existence grounding | `verification/grounding.py`, `verification/object_verifier.py` | Uses Grounding DINO; evidence includes bounding boxes and scores. |
| Same-region attribute verification | `verification/attribute_verifier.py` | Uses the Grounding DINO box crop and a CLIP color-alignment probe. |
| Reliability score | `reliability/engine.py` | Handles unavailable token probabilities without inventing values. |
| Four-way decision | `reliability/engine.py`, `correction/engine.py` | Supports accept, correct, rerank, and abstain. |
| Provenance / audit | `frontend_adapter.py`, `database/db.py` | Stores image hash, candidates, claims, evidence, configuration, decisions, corrections, and latency. |
| POPE / CHAIR / Winoground / SugarCrepe | `evaluation/` | Reporting harnesses are present; datasets/results are not bundled. |

### Known scope limits

- Region-level probing is currently implemented for **color** bindings. Material and other attribute types deliberately return `AMBIGUOUS` until a suitable probe is configured.
- The rule-based claim parser does not yet understand every English phrasing or unrestricted object vocabulary.
- Count and spatial relation checks rely on the Grounding DINO localizations.
- Grounding DINO and CLIP must be downloaded/cached before a live verification can succeed. If either is unavailable, the toolkit reports `AMBIGUOUS`; it does not fabricate evidence.
- Default thresholds and reliability weights are starting configuration values. They require calibration on a held-out labelled split before they can be treated as validated settings.

## Architecture

```text
Input image + user query
        |
        v
Configurable VLM generation engine
        |
        v
Repeated candidate generation (n candidates)
        |
        v
Atomic claim extraction
        |
        +--> existence claim: <object>
        +--> binding claim:  <object, attribute>
        |
        v
Grounding DINO object localization
        |
        +--> object score: s_obj(o) = max d_b
        |
        v
Crop-level CLIP attribute probe
        |
        +--> binding score: s_attr(o,a) = max[d_b * P(a | crop_b)]
        |
        v
Reliability scoring + candidate agreement
        |
        v
ACCEPT / CORRECT / RERANK / ABSTAIN
        |
        v
Dashboard + SQLite / JSON audit record
```

### Why crop-level verification matters

For an image with a **red car** and a **blue bicycle**, a claim that says "blue car" is not validated merely because blue appears in the image. The system first grounds the *car*, crops the car region, and scores colors on that crop. A high red score on the car crop can support an evidence-backed correction from "blue car" to "red car".

## Models

### Visual verification models

| Role | Default model | Purpose |
|---|---|---|
| Open-vocabulary object grounding | `IDEA-Research/grounding-dino-tiny` | Detects claimed objects and returns boxes plus confidences. |
| Region-level color probe | `openai/clip-vit-base-patch32` | Compares color prompts against the cropped grounded object. |

These weights are loaded lazily from Hugging Face on the first live verification. After they are cached, set `verification.local_files_only: true` in `config/config.yaml` to run without further Hugging Face downloads.

### Generator VLM options

Select a provider in the dashboard and configure one of the following in `.env`:

| Provider | Required variables | Example model variable |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `OPENAI_MODEL=gpt-4.1-mini` |
| Groq OpenAI-compatible endpoint | `GROQ_API_KEY` | `GROQ_MODEL=<vision-capable-model>` |
| Gemini | `GEMINI_API_KEY` | `GEMINI_MODEL=<vision-capable-model>` |
| Llama / compatible local or hosted endpoint | `LLAMA_BASE_URL` and usually `LLAMA_API_KEY` | `LLAMA_MODEL=<vision-capable-model>` |

The selected model must accept image input. The toolkit does not supply a generator model or an API key.

## Prerequisites

- macOS, Linux, or Windows with Python 3.10+ (the current environment uses Python 3.14)
- Node.js 20+ and Corepack for the Next.js dashboard
- Internet access on the first run to download Python packages, frontend packages, Grounding DINO, and CLIP weights
- A valid image-capable VLM provider account/key for live response generation

## Setup - first time only

Run the following commands from a terminal. Do **not** copy the lines beginning with `#`; they are explanatory comments and some zsh installations try to execute them.

```bash
cd /Users/skye28/Documents/ChatGPT/vlm

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt

test -f .env || cp .env.example .env
```

Open `.env` in an editor and replace the placeholder values for exactly one provider. For example, with OpenAI:

```dotenv
OPENAI_API_KEY=your_real_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Do not commit `.env` or share API keys.

## Run the dashboard

### Option A - recommended one-command launcher

```bash
cd /Users/skye28/Documents/ChatGPT/vlm
source .venv/bin/activate
./dev-frontend.sh
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Keep this terminal open while using the project. Stop it with `Ctrl-C`.

The launcher starts/reuses:

- Python API adapter: `http://127.0.0.1:8010`
- Next.js dashboard: `http://127.0.0.1:3000`

### Option B - run backend and frontend separately

Terminal 1:

```bash
cd /Users/skye28/Documents/ChatGPT/vlm
source .venv/bin/activate
python3 frontend_adapter.py
```

Terminal 2:

```bash
cd /Users/skye28/Documents/ChatGPT/vlm/frontend
corepack pnpm install
corepack pnpm dev
```

Then visit [http://127.0.0.1:3000](http://127.0.0.1:3000).

### Confirm that the backend is running

```bash
curl http://127.0.0.1:8010/health
```

Expected output:

```json
{"status":"ok"}
```

## If you see “Address already in use” on port 8010

This is the error in the supplied terminal output. It normally means the backend is already running, so **do not start `frontend_adapter.py` again**.

First verify it:

```bash
curl http://127.0.0.1:8010/health
```

If it returns `{"status":"ok"}`, start only the frontend (or use `./dev-frontend.sh`, which reuses it).

If you intentionally need to stop the process occupying port 8010:

```bash
lsof -nP -iTCP:8010 -sTCP:LISTEN
kill <PID_SHOWN_BY_LSOF>
```

Then run `python3 frontend_adapter.py` again. Use `kill` only after checking that the listed process is the old VLM backend you want to stop.

To run the application on other ports instead:

```bash
VLM_API_PORT=8011 VLM_WEB_PORT=3001 ./dev-frontend.sh
```

## Use the dashboard

1. Open `http://127.0.0.1:3000`.
2. Upload a PNG, JPG, or WEBP image (up to 15 MB).
3. Select the generator provider that matches your `.env` configuration.
4. Choose the number of candidates (1 to 3).
5. Enter a question, for example: `Describe the objects and their colors.`
6. Select **Run reliability analysis**.
7. Inspect the output:
   - original generated response;
   - each candidate and normalized claims;
   - Grounding DINO bounding boxes on the image;
   - status and score for every claim;
   - crop-based attribute evidence and alternative observed color, if any;
   - candidate reliability, agreement, decision, and corrected response;
   - audit entry in the Experiments page.

The first live analysis can take noticeably longer because Hugging Face downloads the visual verifier model weights.

## Configuration

All main controls are in [`config/config.yaml`](config/config.yaml).

| Setting | Default | Meaning |
|---|---:|---|
| `generation.num_candidates` | 3 | Candidate count for repeated controlled calls. |
| `verification.grounding_threshold` | 0.30 | Minimum Grounding DINO score for object support. |
| `verification.attribute_threshold` | 0.50 | Minimum region-probe score for a supported/correcting color. |
| `decision.tau_lo` | 0.30 | Lower decision threshold. |
| `decision.tau_hi` | 0.70 | Higher acceptance threshold. |
| `reliability.lambda_verification` | 0.60 | Visual-verification contribution. |
| `reliability.lambda_probability` | 0.20 | Native token-confidence contribution, if truly supplied. |
| `reliability.lambda_agreement` | 0.20 | Candidate-agreement contribution. |

The reliability weights should sum to 1. If the generator does not expose genuine token probabilities, the configured probability weight is redistributed across usable signals and the audit record says that token probability is unavailable.

## Deterministic paper-example demonstration

Run the paper’s illustrative red-shirt / blue-jeans / no-surfboard correction without API keys or model downloads:

```bash
cd /Users/skye28/Documents/ChatGPT/vlm
source .venv/bin/activate
python3 demo_paper_example.py
```

Expected corrected text:

```text
A person in a red shirt and blue jeans stands on the beach.
```

This is an explicitly labelled **evidence fixture** for deterministic demonstration. It is not a claim that Grounding DINO or CLIP ran on a real beach image.

## Tests

```bash
cd /Users/skye28/Documents/ChatGPT/vlm
source .venv/bin/activate
python3 -m pytest -q
```

The suite currently checks claim decomposition, exact object-score behavior, missing-object evidence, crop-only color binding, unavailable-backend abstention, correction, agreement, unavailable token-confidence redistribution, and calibration minimum-sample behavior.

## Evaluation and research experiments

Benchmark adapters require prepared labelled JSONL data. They do not download datasets or invent labels/results.

```bash
python3 -m evaluation.run_benchmarks \
  --data data/benchmarks \
  --out results/benchmark_report.json
```

Expected optional input files:

| File | Required fields / result |
|---|---|
| `pope.jsonl` | `split`, `label`, `prediction`; reports random/popular/adversarial accuracy, precision, recall, F1, yes-ratio. |
| `chair.jsonl` | `ground_truth_objects`, `mentioned_objects`; reports CHAIR-S, CHAIR-I, object recall. |
| `winoground.jsonl` | `text_correct`, `image_correct`; reports text, image, group scores. |
| `sugarcrepe.jsonl` | `category`, `correct`; reports replace, swap, add. |

`evaluation/ablations.py` defines the intended experiments: base VLM, full toolkit, no attribute verifier, no reliability score, and `n=1`. `evaluation/metrics.py` computes Brier score and ECE only from labelled data; ECE requires at least 30 labelled records.

## Repository map

```text
vlm/
├── app.py                         # legacy Streamlit UI
├── frontend_adapter.py             # Python HTTP API and audit persistence
├── vlm.py                          # VLM provider adapters
├── vlm_engine.py                   # interchangeable generation abstraction
├── core/                           # pipeline and typed schemas
├── claims/                         # claim normalization, extraction, graph
├── verification/                   # Grounding DINO + crop attribute verifier
├── reliability/                    # agreement and candidate reliability scoring
├── correction/                     # conservative text corrections
├── evaluation/                     # benchmark runners, metrics, reports, ablations
├── database/                       # SQLite experiment history
├── frontend/                       # Next.js research dashboard
├── tests/                          # unit and methodology tests
├── config/config.yaml              # thresholds, models, reliability weights
└── results/                        # SQLite DB and generated reports
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `zsh: command not found: #` | A comment line was pasted into zsh. It is harmless; copy commands only, not explanatory `#` lines. |
| `OSError: [Errno 48] Address already in use` | Backend already owns port 8010. Check `/health`; reuse it or stop the known process. |
| Provider request fails | Verify the selected provider has a real API key and an image-capable model ID in `.env`. |
| Grounding/CLIP evidence is `AMBIGUOUS` | First weight download may have failed or no internet/cache exists. Read the returned evidence explanation. |
| Dashboard is unavailable | Confirm backend health, then run the frontend in `frontend/` or use `./dev-frontend.sh`. |
| `pnpm install` cannot download | Restore network access and rerun `corepack pnpm install`; the frontend requires its Node dependencies. |

## Research limitations

This toolkit is a research implementation, not a validated safety system. Detector misses, crop ambiguity, VLM generation errors, and rule-parser coverage can affect outcomes. Calibration and benchmark claims must come from documented runs on held-out data. The project does not address reasoning errors, toxicity, or adversarial robustness.
