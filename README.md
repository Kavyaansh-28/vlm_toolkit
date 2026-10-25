# VLM Reliability Layer

**A model-agnostic verification, reliability-scoring, and correction layer for existing vision-language models.** This project does not train or replace a VLM. A selected generator produces the original response; a separate, image-grounded verifier checks atomic claims and supports a conservative accept, correct, rerank, or abstain decision.

## Research pipeline

```text
image + question
  -> selected generator VLM
  -> preserved original response
  -> typed claim decomposition + claim graph
  -> independent VLM verifier (claims batched in one image call)
  -> evidence fusion + reliability score
  -> accept / correct / rerank / abstain
  -> SQLite experiment history
```

There is **no YOLO or object detector** in the verification path. The verifier receives the image and atomic claim fields—not the generator's prose or reasoning—and returns a structured status, observed value, confidence estimate, and explanation. It checks entity-attribute binding, quantities, and relations as well as object claims. A missing, malformed, or ambiguous verifier result stays `AMBIGUOUS`; it is not silently converted into support or contradiction.

Verifier confidence is the VLM's self-reported estimate and is explicitly **uncalibrated**. Provider token probabilities are not available in the current adapters, so they are not fabricated. If a probability weight is configured but no genuine probability is available, that weight is redistributed to visual verification. The actual model probability row remains `Unavailable` in the UI.

## Providers and configuration

Generator and verifier can be selected independently. Both use the same provider adapter interface; they can use the same model or different providers for cross-model experiments.

Supported adapters:

- `openai` — OpenAI-compatible vision chat models
- `gemini` — Gemini vision models
- `groq` — Groq's OpenAI-compatible vision endpoint; choose a vision-capable model in configuration
- `llama` — an OpenAI-compatible Llama vision endpoint, including a local serving endpoint

Copy `.env.example` to `.env` and add credentials/configuration there. Secrets stay on the Python server and are never sent to the browser.

```dotenv
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=
GROQ_MODEL=qwen/qwen3.8-27b
LLAMA_BASE_URL=http://localhost:8000/v1
LLAMA_API_KEY=optional_for_local_server
LLAMA_MODEL=Llama-3.2-11B-Vision-Instruct
```

Provider names may appear in the selector even when credentials are absent; selecting an unconfigured provider returns an explicit configuration error. The configured model must support image input. Availability and exact model IDs depend on the endpoint/account configuration.

## Install and run

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
cd frontend && corepack pnpm install && cd ..
./dev-frontend.sh
```

The frontend is at `http://127.0.0.1:3000`; the local compatibility adapter is at `http://127.0.0.1:8010`. To run separately, use `python3 frontend_adapter.py` and `cd frontend && corepack pnpm dev` in two terminals. The legacy Streamlit UI remains available with `streamlit run app.py` and uses the same pipeline.

## Reliability and decisions

The scorer uses claim verification, candidate agreement, and model probability when genuinely supplied:

`R = λv · V + λp · P + λa · A`, where weights sum to 1.

Current providers do not supply usable token probabilities. Their configured `λp` is redistributed to `λv`; no mock probability enters either the backend score or the UI. Agreement is not visual truth and cannot cancel a high-confidence contradiction. Evidence results are one of `SUPPORTED`, `CONTRADICTED`, `UNSUPPORTED`, or `AMBIGUOUS`.

- **ACCEPT** when evidence meets the configured accept threshold without a major contradiction.
- **CORRECT** only when the verifier contradicts a claim with sufficiently strong evidence and provides an evidence-backed alternative where needed.
- **RERANK** only when another candidate is materially stronger and meets the accept policy.
- **ABSTAIN** when evidence is missing, ambiguous, or insufficient.

The correction layer changes only supported attribute/count claims or removes an object positively contradicted by the verifier. It does not treat `UNSUPPORTED` or `AMBIGUOUS` as proof of error.

Error taxonomy includes `OBJECT_HALLUCINATION`, `ATTRIBUTE_ERROR`, `ATTRIBUTE_BINDING_ERROR`, `QUANTITY_ERROR`, `RELATION_ERROR`, `UNSUPPORTED_CLAIM`, `CONTRADICTED_CLAIM`, `AMBIGUOUS_CLAIM`, and `MULTI_CLAIM_CONTRADICTION`.

## API endpoints

- `GET /api/config` — configured provider choices and analysis defaults
- `POST /api/analyze` — image, query, generator provider, optional verifier provider, candidate count, and reliability policy
- `GET /api/evaluation` — labelled evaluation metrics (empty until labelled rows exist)
- `GET /api/history` — recent SQLite experiment summaries
- `GET /api/history/{id}` — full stored candidate/claim/evidence output
- `GET /health` — adapter health

Each candidate stores its original response, typed claims, verifier evidence, reliability, decision, correction, generator/verifier provider and model, and latency. The source image is not stored in experiment history.

## Evaluation and reproducibility

`evaluation/metrics.py` computes metrics only from labelled records; calibration requires at least 30 samples. No external benchmark results are claimed. Run the focused/unit suite with:

```bash
python3 -m pytest -q
```

The tests mock the verifier response to exercise claim binding, contradiction handling, abstention, correction, agreement veto, and calibration thresholds without fabricating live model results.

## Frontend

`frontend/` is the existing Next.js 16 App Router / React 19 research interface. It shows separate generator/verifier selectors, real claims and returned verifier explanations, decision/reliability state, candidate comparisons, evaluation empty states, and SQLite history. Simulated probabilities have been removed. The UI labels verifier confidence as uncalibrated and keeps model token probability unavailable unless an adapter genuinely supplies it.

## Limitations

- Claim extraction is deterministic and currently covers a limited vocabulary of object, color, quantity, and spatial-language patterns; it can miss paraphrases and complex semantics.
- VLM verification is a second model judgment, not ground truth. Self-reported confidence is not calibrated, and same-provider verification may share generator biases; cross-provider selection is available where configured.
- Provider calls add latency and cost. Claims are batched into one verifier call per candidate, but there is no caching or benchmark dataset adapter yet.
- Image boxes are not produced by the VLM verifier. The interface presents claim evidence and graph bindings without inventing bounding boxes.
- Evaluation remains unpopulated until users supply labeled records; no accuracy, calibration, or benchmark gains are asserted.
