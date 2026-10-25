# VLM Reliability Toolkit — 1-Day Implementation Plan ($0 edition: Kaggle GPU + Hugging Face Hub)

**Team:** Prithvi · Harsh · Yash · Kavyansh
**Deadline:** tomorrow. **Code freeze at H+18**; everything after that is buffer.
**Scope (agreed):** a demo-ready, paper-faithful pipeline with **POPE** and **CHAIR** results. Benchmarks run on **Kaggle's free GPU notebooks (GPU T4 x2)**. Results are shared through a **free Hugging Face dataset repo**. The **dashboard stays local**. **Budget: $0.**
**Workflow rule:** ⛔ no direct pushes to `main`. Every change goes through a reviewed Pull Request (see §5 "Git rules").
**Out of scope:** Winoground, SugarCrepe (a P2 stretch is defined), scene/location claims ("location is beach"), relation *correction*. BLIP-2 is a P2 stretch, POPE only.

---

## ✅ Implementation status (branch `feat/full-paper-implementation`)

All code tasks in this plan (S0, P1–P5, H1–H6, Y1–Y5, K1–K4) are implemented on the branch above. Y6 (LLM extractor) and Y7 (SugarCrepe) remain stretch goals. The code was not split per person; the task list below still works as a map of where things live and how to test them.

**What remains is running it, not building it:**
1. Review and merge the PR (Git rules in §5).
2. Phase 0 accounts: Kaggle phone verification, HF org + dataset repo, `HF_TOKEN` secret.
3. Kaggle smoke run (`BENCHES=["smoke"]`), then the full run (`["pope","chair"]`). See README "Benchmarks".
4. `python -m evaluation.run_benchmarks` → `results/RESULTS.md`, then commit that file via a PR.
5. Add demo photos to `test_images/` and rehearse `demo/DEMO.md`.

**Verified locally:**
- 62 tests pass.
- Frontend typecheck and build pass.
- Real Grounding DINO + CLIP ran on a COCO image on CPU, and hallucinated objects were deleted.
- A real re-rank went through the dashboard API.
- The `hf-local` engine produced a token-probability answer with LLaVA-OneVision-0.5B.

---

## 0. Where we are, and how much of the paper this plan covers

**Today:** about 45% of the paper is implemented. The pipeline (claims → Grounding DINO → CLIP crop → score → correct → SQLite) works with API VLMs. The Next.js dashboard works. Eq. 1, and Eq. 2 for colour, are correct.

**After this plan:**

| Paper section | Coverage after plan | Notes |
|---|---|---|
| Contribution 1: unified claim diagnostic | ✅ 100% | Existence and binding claims go through one pipeline |
| Contribution 2: reliability score + accept/correct/re-rank/abstain, calibrated | ✅ ~90% | λ₁/λ₂ and lo/hi tuned on a held-out split, with ECE reported. λ₃ stays at its default (needs n>1 labels) |
| Contribution 3: one harness for POPE, CHAIR, Winoground, SugarCrepe | ⚠️ ~50% | POPE and CHAIR are fully done. Winoground, SugarCrepe and the matching-benchmark adaptation are not (SugarCrepe-attribute is a stretch) |
| Contribution 4: model-agnostic implementation + dashboard + provenance | ✅ 100% | API VLMs + local HF LLaVA, FastAPI, Next.js, audit log, review queue |
| §III formulation, §IV-A architecture (7 components) | ✅ 100% | |
| §IV-B n-best + rule-and-LLM extractor | ✅ ~85% | Real sampled n-best. Rule extractor covers all 80 COCO classes. The LLM extractor is optional (P2, demo only) |
| §IV-C Eq. 1, Eq. 2 (colour, material, count, spatial) | ✅ 100% | |
| §IV-D Eq. 3 with real p_j and A_j | ✅ 100% | |
| §IV-E decision and correction policy + audit log | ✅ 100% | |
| §V-A metrics (POPE, CHAIR, latency, abstention, calibration) | ✅ 100% for POPE/CHAIR | |
| §V-A coverage, ≥500 images per split | ⚠️ ~95% | CHAIR 500. POPE 450 per split: POPE has only 500 images, and 50 are reserved for tuning |
| §V-C baselines (LLaVA, BLIP-2) and ablations | ⚠️ ~80% | LLaVA ✅ and all 4 ablations ✅. BLIP-2 is a stretch |
| §V-D implementation (PyTorch, HF, ≥16 GB GPU, FastAPI, Next.js) | ✅ 100% | The Kaggle T4 (16 GB) is exactly the paper's "≥16 GB, e.g. NVIDIA T4" recommendation |
| §VI illustrative example (Table IV) | ✅ ~90% | Everything except the "location is beach" claim |
| **Overall** | **≈ 85%** (≈ 88% with the BLIP-2 stretch) | |

**One honest caveat to put in the paper:** POPE and CHAIR only measure object hallucination. The attribute-binding verifier, which is our main novelty, is shown qualitatively (Table IV demo + dashboard), but nothing measures it quantitatively until SugarCrepe or Winoground is run. The "no attribute binding" ablation will show no change on POPE or CHAIR, and that's expected.

---

## 1. Budget ($0) and free accounts

| Need | Free resource | Limits to respect |
|---|---|---|
| GPU for POPE/CHAIR | **Kaggle notebook, accelerator "GPU T4 x2"** (2 × 16 GB) | Weekly quota of roughly 30 GPU-hours (the exact figure is in Kaggle → Settings, and it floats). Max **12 h per session**. A phone-verified account is required for GPU + Internet |
| Sharing results + resume | **Free HF org + private dataset repo** | Free for this size (a few hundred MB of JSONL) |
| Live demo VLM | **Gemini free-tier key** (already supported) | Free-tier rate limits; fine for a demo |
| Demo verification | Mac (MPS), locally | — |
| Development / smoke / fallback GPU | Lenovo RTX 3050 6 GB | 4-bit or the 0.5B model only |

**Estimated GPU use:** smoke ~0.5 h + full run ~4 h wall-clock = **~4.5 of ~30 free hours**. The quota is counted per session-hour, so using both T4s at once costs nothing extra. That leaves room for one complete rerun and the stretch tasks.

**Accounts (H+0):**
1. **Prithvi and Kavyansh:** create Kaggle accounts and **phone-verify** them (Settings → Phone verification). Without it there's no GPU and no Internet. Two accounts give two independent quotas, so the second is the backup if one is queued or runs out.
2. **Prithvi:** results live in the dataset repo `Prithxvhie44/vlm-results` on Prithvi's personal Hugging Face account (no organisation needed). If it is private, teammates download with a read token from Prithvi; if public, no token is needed to read.
3. **Prithvi:** create an HF **write** token scoped to the org. Teammates create **read** tokens for downloading results. Never commit tokens.
4. If the GitHub repo is private, create a fine-grained, read-only GitHub token (`GH_TOKEN`).
5. In the Kaggle notebook: **Add-ons → Secrets** → add `HF_TOKEN` (and `GH_TOKEN`). In **Settings**, set Accelerator = **GPU T4 x2**, Internet = **On**, Persistence = Files.

---

## 2. Key design decisions (read before coding)

1. **Benchmarks run in one Kaggle notebook, not on laptops.** The notebook clones the repo, installs, prepares data and pre-downloads the weights once. It then launches **two background processes in parallel: POPE on GPU 0 and CHAIR on GPU 1** (`CUDA_VISIBLE_DEVICES`). Each runs **generate → process → push results**. It's started with **Save Version → "Save & Run All (Commit)"**, which keeps running with the browser closed (up to 12 h).
2. **Still two stages, with cached files.** `generate` writes `results/gen/*.jsonl`. `process` writes `results/proc/<ablation>/*.jsonl`. Both are **resumable**, and each process **pushes partial results to the HF dataset repo every 100 samples**. If the session dies, re-running the notebook pulls the partial files and continues, losing at most ~100 samples.
3. **The verification cache makes reprocessing free.** Grounding DINO boxes/scores and CLIP crop probabilities are cached per `(image_sha256, object[, box, attribute_type])` and pushed with the results. After the run, **any laptop (CPU, no models)** can rerun `process` with new thresholds, λ or ablations in minutes. Tuning and ablations cost no GPU quota.
4. **Candidate 1 is always greedy decoding.** It's the *uncorrected baseline* (§V-C). Candidates 2..n are sampled at `temperature=0.7` (agreement signal). POPE uses n=1 (yes/no answers).
5. **Base VLM:** `llava-hf/llava-1.5-7b-hf` in **fp16 on one T4** (~13.5 GB of weights in 15 GB). It fits because generation runs in its own process, and Grounding DINO/CLIP only load later in the process stage. **If it runs out of memory, set `vlm.hf_precision: 4bit`** (bitsandbytes works on Kaggle's Linux) and state that in the paper. Laptop development uses `llava-hf/llava-onevision-qwen2-0.5b-ov-hf` on the Lenovo/Mac, or the fake engine in tests.
6. **p_j = exp(mean log-prob of generated tokens)**, computed from raw logits (`output_logits=True`). This is the length-normalised sequence probability.
7. **POPE toolkit policy.** A VLM "yes" asserts the existence claim ⟨obj⟩, so `v = s_obj`. If the claim action is CORRECT (delete), the final answer is **no**. ACCEPT gives **yes**. ABSTAIN keeps **yes** and counts toward the abstention rate. A "no" asserts nothing, so it's unchanged (the paper verifies only asserted content).
8. **Splits:** 50 of POPE's 500 COCO images (seed 42) form the **held-out tuning split**. They're never used in reported numbers. POPE eval = the other 450 images × 3 splits. CHAIR = 500 COCO val2014 images (the 450 POPE eval images + 50 more), disjoint from the tune split.
9. **Live demo:** local dashboard + local Grounding DINO/CLIP on the Mac (MPS), with the VLM on the **Gemini free tier**. p_j shows "n/a" for API models, and that's honest. p_j comes from the `hf-local` engine, which is shown in the benchmark results. Show it live on the Lenovo with the 0.5B model if time allows.

---

## 3. Interface contracts (agree at H+0; don't change without telling everyone)

### 3.1 Schema changes (`core/schemas.py`; Harsh pushes these **within the first 45 min**)
```python
@dataclass
class Candidate:
    ...existing fields...
    agreement_available: bool = False          # False when n == 1
    num_tokens: int | None = None
    claim_actions: dict[str, str] = field(default_factory=dict)   # claim_id -> ACCEPT|CORRECT|ABSTAIN
    claim_values: dict[str, float] = field(default_factory=dict)  # claim_id -> v_i used by the policy
    action_details: dict[str, str] = field(default_factory=dict)  # claim_id -> "delete"|"replace:red"|"swap:shirt<->jeans"
    selected: bool = False                     # the candidate returned to the user
```
Candidate `decision` is one of `ACCEPT | CORRECT | RERANK | ABSTAIN`. The names are unchanged, so the frontend keeps working.

### 3.2 VLM engine (`vlm_engine.py`; Prithvi)
```python
engine.generate_candidates(image_path, query, n, temperature=0.7, max_new_tokens=128, seed=42) -> list[dict]
# each dict: {"response", "model", "probability": float|None, "probability_available": bool,
#             "num_tokens": int, "latency_ms": int, "generation_strategy": "greedy"|"sampled"|"repeated_api_calls", "error"}
```
Providers: existing `openai | groq | gemini | llama`, plus new **`hf-local`** (transformers on this machine's GPU). *Optional:* `hf-router` (HF Inference Providers). Free accounts get only a tiny monthly credit, so it isn't used for the demo.

### 3.3 Pipeline (`core/pipeline.py`; Harsh)
```python
@dataclass
class PipelineConfig:
    lo: float; hi: float; rerank_threshold: float
    weights: dict[str, float]            # verification / probability / agreement
    grounding_threshold: float
    verification: bool = True
    attribute_verifier: bool = True
    reliability: bool = True             # False => no R-based rerank/abstain (ablation)
    candidate_count: int = 3

def load_config(path="config/config.yaml", tuned="results/tuned.yaml") -> PipelineConfig   # tuned.yaml overrides if present
def process_candidates(image_path: str, rows: list[dict], cfg: PipelineConfig) -> list[Candidate]   # SELECTED first
def run(image_path, query, provider, cfg, manual_text="") -> tuple[list[Candidate], str | None]     # live path
```

### 3.4 Policy (`core/policy.py`; Harsh)
```python
def claim_action(v: float, evidence: Evidence | None, claim: Claim, cfg: PipelineConfig) -> str  # ACCEPT|CORRECT|ABSTAIN
```

### 3.5 Data files
`data/benchmarks/pope_{random,popular,adversarial}.jsonl`, `pope_tune.jsonl` (Yash):
```json
{"sample_id": "pope-random-000123", "benchmark": "pope", "split": "random", "image_id": 310196,
 "image_path": "data/images/COCO_val2014_000000310196.jpg", "object": "dining table",
 "query": "Is there a dining table in the image? Answer yes or no.", "label": true}
```
`data/benchmarks/chair.jsonl` (Yash):
```json
{"sample_id": "chair-000042", "benchmark": "chair", "split": "all", "image_id": 310196,
 "image_path": "data/images/COCO_val2014_000000310196.jpg",
 "query": "Describe this image in detail.", "gt_objects": ["person", "dining table", "cup"]}
```
`results/gen/{bench}_{split}.jsonl` (Prithvi's generate stage = the input record plus):
```json
{"model": "llava-hf/llava-1.5-7b-hf", "precision": "fp16", "hardware": "kaggle:t4",
 "generation": {"n": 3, "temperature": 0.7, "seed": 42, "max_new_tokens": 128},
 "candidates": [{"text": "...", "probability": 0.81, "num_tokens": 97, "latency_ms": 2900, "strategy": "greedy"}]}
```
`results/proc/{ablation}/{bench}_{split}.jsonl` (Harsh's process stage):
```json
{"sample_id": "...", "benchmark": "chair", "split": "all", "ablation": "full_toolkit",
 "base_text": "...", "final_text": "...", "decision": "CORRECT", "selected_candidate": 0, "reliability": 0.71,
 "claim_actions": {"C-ab12": "CORRECT"}, "action_details": {"C-ab12": "delete"},
 "pope": {"base_answer": true, "final_answer": false, "v": 0.04, "p": 0.93, "abstained": false},
 "latency_ms": {"generation_base": 2900, "generation_all": 8400, "verification": 1100, "total": 9500, "measured_on": "kaggle:t4"}}
```
`label` and `gt_objects` are copied through. `pope` is present only for POPE rows. When reprocessing from cache, the **latency fields are kept from the Kaggle first pass**, never re-measured on a laptop.

`results/cache/verification.jsonl` (Kavyansh): `{"key": "<sha256>|<object>", "boxes": [...], "scores": [...]}` and `{"key": "<sha256>|<object>|<box>|color", "probs": {...}}`.

### 3.6 API (Prithvi). Existing routes stay identical; new ones added
| Method | Route | Notes |
|---|---|---|
| GET | `/health`, `/api/config`, `/api/history`, `/api/history/{id}`, `/api/evaluation` | unchanged |
| POST | `/api/analyze` | unchanged request; candidates gain the §3.1 fields |
| GET | `/api/benchmarks` | `results/benchmark_report.json` or `{"status":"NOT RUN"}` |
| GET | `/api/review` | flagged claims `[{experiment_id, candidate_id, claim_id, claim_text, v, explanation, region_crop, label}]` |
| POST | `/api/review` | `{experiment_id, claim_id, label: "correct"|"incorrect"|"unsure", note}` → SQLite `annotations` |

Port stays **8010**.

---

## 4. File ownership (avoids merge conflicts)

| Owner | Files |
|---|---|
| **Prithvi** | `vlm.py`, `vlm_engine.py`, `models/hf_vlm.py`, `evaluation/generate.py`, `evaluation/hub_sync.py`, `jobs/run_eval.sh`, `kaggle/` (notebook), `api/server.py` (FastAPI), `frontend_adapter.py` (retire), `database/db.py`, `requirements*.txt`, `scripts/` |
| **Harsh** | `core/*` (incl. `core/policy.py`), `reliability/*`, `correction/*`, `config/config.yaml`, `evaluation/process.py`, `evaluation/ablations.py`, legacy deletions, `tests/test_policy.py`, `tests/test_pipeline.py` |
| **Yash** | `claims/*` (incl. `claims/vocab.py`, `data/coco_synonyms.txt`), `evaluation/prepare_data.py`, `evaluation/chair.py`, `evaluation/evaluator.py`, `evaluation/metrics.py`, `evaluation/reports.py`, `evaluation/run_benchmarks.py`, `evaluation/tune.py`, `tests/test_extractor.py`, `tests/test_chair.py`, `tests/test_eval.py` |
| **Kavyansh** | `verification/*`, `utils.py` (device helper), `frontend/*`, `test_images/`, `demo/`, `README.md`, `tests/test_verification.py` |

Message the owner before touching their file.

---

## 5. Setup (H+0 → H+1)

### Git rules (mandatory for everyone, including Prithvi)

> ⛔ **Never push code directly to `main`.** Every change goes through a Pull Request, and nothing is merged without one.

1. **Branch from an up-to-date `main`:**
   ```bash
   git checkout main && git pull
   git checkout -b feat/<name>-<task-id>        # e.g. feat/harsh-H3-policy, feat/yash-Y2-extractor
   ```
2. **Commit small and often on your branch**, then push the branch (never `main`):
   ```bash
   git add <your files> && git commit -m "H3: per-claim decision policy"
   git push -u origin feat/<name>-<task-id>
   ```
3. **Open a PR into `main`** on GitHub (or `gh pr create --base main`). The PR description must include:
   - the task ID(s) from this plan
   - what changed
   - **how you tested it**: the `pytest` output plus any manual check from the task's "How to test"
4. **Before requesting review:** `git pull origin main` into your branch, resolve conflicts, and run `python -m pytest -q` (and `corepack pnpm build` for frontend changes). The result must be green.
5. **Review and merge:** at least **one other teammate approves**. **Prithvi merges** with *Squash and merge*. Prithvi's own PRs are reviewed and merged by Harsh. Never merge a PR with failing tests.
6. **After a merge:** everyone pulls `main` at each checkpoint (H+3, H+5, H+7) and rebases or merges it into their open branches.
7. **Recommended (2 min, Prithvi at H+0):** GitHub → Settings → Branches → add a protection rule for `main` with "Require a pull request before merging" and 1 approval. Then direct pushes are blocked, not just discouraged.

**Not code, so no PR needed:** benchmark outputs pushed by the Kaggle notebook to the **HF dataset repo**. These never go into the Git repo, because `results/gen`, `results/proc` and `results/cache` are git-ignored. `results/RESULTS.md` and `results/benchmark_report.json` *do* go into Git, through a normal PR.

**All four laptops:**
```bash
python -m venv .venv            # Python 3.11 or 3.12
# Windows: .venv\Scripts\Activate.ps1     macOS: source .venv/bin/activate
pip install --upgrade pip && pip install torch torchvision && pip install -r requirements.txt
pip install -U "huggingface_hub[cli]" && hf auth login      # read token (Prithvi: write token)
python -m pytest -q
```
**Mac (demo machine):** `export PYTORCH_ENABLE_MPS_FALLBACK=1` (add it to `~/.zshrc`), then pre-download the verifiers:
`python -c "from huggingface_hub import snapshot_download as d; [d(m) for m in ['IDEA-Research/grounding-dino-tiny','openai/clip-vit-base-patch32']]"`

### S0. Prithvi pushes in the first 30 min, before anyone else edits requirements
- `requirements.txt`: add `fastapi>=0.115`, `uvicorn[standard]>=0.30`, `accelerate>=0.34`, `datasets>=2.20`, `huggingface_hub>=0.34`, `tqdm>=4.66`, `pytest>=8.0`. Pin `transformers>=4.45,<5`. Leave out `streamlit`, `streamlit-paste-button` and `plotly` (legacy UI).
- `requirements-cuda.txt`: `bitsandbytes>=0.44` (4-bit fallback on Kaggle or the Lenovo). Don't pin a `torch` version: Kaggle's preinstalled CUDA torch must not be replaced.
- Delete the unused root `package.json` / `package-lock.json`.
- `.gitignore`: add `data/`, `results/gen/`, `results/proc/`, `results/cache/`, `results/tuned.yaml`, `.env`. Keep `data/coco_synonyms.txt` with a `!data/coco_synonyms.txt` exception.
- Like every change, S0 goes in through a PR. Ask Harsh for a fast review so the others can branch off it.
- `.env.example`: add `HF_TOKEN=`, `HF_ROUTER_MODEL=`, `RESULTS_REPO=Prithxvhie44/vlm-results`.

---

## 6. Phase plan

| Phase | Window | Goal | Exit check |
|---|---|---|---|
| **0. Setup and contracts** | H+0 → H+1 | Kaggle accounts phone-verified; HF org + dataset repo; environments; §3 contracts; schema + requirements pushed | `pytest` green everywhere; `hf auth whoami` works; Kaggle notebook shows 2 × T4 (`!nvidia-smi`) |
| **1. Parallel build** | H+1 → H+5 | All P0 tasks with unit tests | PRs merged |
| ↳ checkpoint 1 | **H+3** | **Infra smoke** in an *interactive* Kaggle session (P1 + P2 + P4 only): 5 POPE questions + 3 CHAIR images, generate only, LLaVA-7B fp16 fits on one T4 | `results/gen/smoke_*.jsonl` in the dataset repo; fp16-vs-4bit decided |
| **2. Integration smoke** | H+5 → H+7 | Full chain smoke (prepare → generate → process → push) on Kaggle; dashboard on FastAPI | `RESULTS.md` built on a laptop from downloaded smoke results; live demo works on the Mac |
| **3. Full run + polish** | H+7 → H+12 | **One "Save & Run All" commit: POPE on GPU 0 and CHAIR on GPU 1 in parallel** (~3.5–4 h wall-clock). Team polishes demo/docs meanwhile | Commit finished; all files in the dataset repo |
| **4. Tune, report, rehearse** | H+12 → H+16 | Tune on held-out data → reprocess from cache on a laptop → final report; stretch runs; demo rehearsal ×2 | `results/RESULTS.md` final; demo rehearsed |
| **Freeze** | H+18 | | |

**If behind, cut in this order:** SugarCrepe stretch → BLIP-2 stretch → Y6 LLM extractor → K2 material probe → H4 swap detail → P3 FastAPI (keep `http.server`) → reduce N (POPE 100 images/split, CHAIR 300). A smaller N only changes the `--limit` flag.

---

## 7. Tasks by person

Priority: **P0** must ship · **P1** should ship · **P2** stretch

---

### PRITHVI: VLM engines, Kaggle runs, backend, integrator

#### P1. `hf-local` engine with real n-best and p_j (P0, ~2.5 h)
**Files:** `models/hf_vlm.py` (new), `vlm_engine.py`, `vlm.py`
```python
import time, torch
from PIL import Image
from transformers import AutoProcessor, LlavaForConditionalGeneration, LlavaOnevisionForConditionalGeneration

class HFVLMEngine:
    def __init__(self, model_id="llava-hf/llava-1.5-7b-hf", precision="fp16", device=None):
        from utils import get_device
        self.device, self.model_id = device or get_device(), model_id
        cls = LlavaOnevisionForConditionalGeneration if "onevision" in model_id else LlavaForConditionalGeneration
        kwargs = {"torch_dtype": torch.float16 if self.device != "cpu" else torch.float32}
        if precision == "4bit":   # T4 budget option only
            from transformers import BitsAndBytesConfig
            kwargs.update(quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                          bnb_4bit_compute_dtype=torch.float16), device_map="auto")
        self.model = cls.from_pretrained(model_id, **kwargs).eval()
        if "device_map" not in kwargs: self.model.to(self.device)
        self.processor = AutoProcessor.from_pretrained(model_id)

    @torch.no_grad()
    def _generate(self, image, query, k, sample, temperature, max_new_tokens):
        conv = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": query}]}]
        prompt = self.processor.apply_chat_template(conv, add_generation_prompt=True)
        inputs = self.processor(images=image, text=prompt, return_tensors="pt").to(self.model.device, self.model.dtype)
        out = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=sample,
                                  temperature=temperature if sample else None, num_return_sequences=k,
                                  return_dict_in_generate=True, output_logits=True)
        logp = self.model.compute_transition_scores(out.sequences, out.logits, normalize_logits=True)  # raw-logit log-probs
        gen = out.sequences[:, inputs["input_ids"].shape[1]:]
        mask = gen != self.processor.tokenizer.pad_token_id
        rows = []
        for i in range(gen.shape[0]):
            lp = logp[i][mask[i]]
            rows.append((self.processor.decode(gen[i][mask[i]], skip_special_tokens=True).strip(),
                         float(lp.mean().exp()) if lp.numel() else None, int(mask[i].sum())))
        return rows

    def generate_candidates(self, image_path, query, n, temperature=0.7, max_new_tokens=128, seed=42):
        image = Image.open(image_path).convert("RGB"); torch.manual_seed(seed)
        results = []
        for strategy, k in (("greedy", 1), ("sampled", n - 1)):
            if k <= 0: continue
            t0 = time.perf_counter()
            rows = self._generate(image, query, k, strategy == "sampled", temperature, max_new_tokens)
            per = round((time.perf_counter() - t0) * 1000 / k)
            results += [{"response": t, "model": self.model_id, "probability": p, "probability_available": p is not None,
                         "num_tokens": nt, "latency_ms": per, "generation_strategy": strategy, "error": None} for t, p, nt in rows]
        return results
```
- Register `hf-local` (model and precision from `config.yaml` → `vlm.hf_model`, `vlm.hf_precision`). *Optional, 5 min:* `hf-router` = `OpenAICompatibleProvider("hf-router", os.getenv("HF_ROUTER_MODEL"), os.getenv("HF_TOKEN"), "https://router.huggingface.co/v1")`. It's not used for the demo, because free HF credits are tiny.
- API providers: **remove the "Candidate sample k of n" prompt suffix**, pass `temperature`, and set `generation_strategy="repeated_api_calls"`. Fix the invalid `DEFAULTS` model ids.

**How to test (laptop, small model):**
```bash
python -c "from models.hf_vlm import HFVLMEngine as E; e=E('llava-hf/llava-onevision-qwen2-0.5b-ov-hf'); print([(r['generation_strategy'], round(r['probability'],3), r['num_tokens']) for r in e.generate_candidates('test_images/demo1.jpg','Describe this image in detail.',3)])"
```
Add `tests/test_engine_contract.py` with a fake engine that asserts the §3.2 keys.
**Done when:** 3 candidates come back, candidate 1 is identical across two runs (greedy), and `0 < p ≤ 1`.

#### P2. Resumable generation stage (P0, ~1 h)
**File:** `evaluation/generate.py`
```text
python -m evaluation.generate --input data/benchmarks/pope_random.jsonl --out results/gen/pope_random.jsonl --n 1 --max-new-tokens 8 [--limit N] [--push-every 100]
python -m evaluation.generate --input data/benchmarks/chair.jsonl --out results/gen/chair.jsonl --n 3 --max-new-tokens 128
```
- Skips `sample_id`s already in `--out` (resume), appends with a `flush()` after each line, shows tqdm progress, logs per-sample errors and continues. With `--push-every`, it calls `hub_sync.push(patterns=[out])` every N samples.

**Test:** `--limit 5`, Ctrl-C midway, rerun → exactly 5 unique `sample_id`s.

#### P4. Kaggle notebook + HF Hub sync (P0, ~1.5 h; needed for checkpoint 1)
**Files:** `evaluation/hub_sync.py`, `jobs/run_eval.sh`, `kaggle/run_benchmarks.ipynb` (plus a copy `kaggle/run_benchmarks.py` for code review)
- `hub_sync.py`. Each process pushes only its own files. Retry, because two processes committing to the same repo can occasionally collide:
```python
import time
from huggingface_hub import HfApi, snapshot_download
def pull(repo):                    # resume: fetch whatever earlier runs pushed
    snapshot_download(repo, repo_type="dataset", local_dir=".", allow_patterns=["results/**"])
def push(repo, patterns, tries=4):
    for i in range(tries):
        try:
            return HfApi().upload_folder(repo_id=repo, repo_type="dataset", folder_path=".",
                                         allow_patterns=patterns, commit_message="kaggle results")
        except Exception as exc:   # concurrent-commit conflict or transient network error
            if i == tries - 1: print(f"push failed, results still in /kaggle/working: {exc}"); return None
            time.sleep(10 * (i + 1))
```
- `jobs/run_eval.sh <bench>` runs from the repo root, where `<bench>` is `pope`, `chair` or `smoke`. Clone, install, data prep and weight download happen **once in the notebook**, so the two parallel processes never race on them:
```bash
#!/usr/bin/env bash
set -euo pipefail
BENCH=$1
if [ "$BENCH" = pope ]; then
  for s in tune random popular adversarial; do
    python -m evaluation.generate --input data/benchmarks/pope_$s.jsonl --out results/gen/pope_$s.jsonl --n 1 --max-new-tokens 8 --push-every 300
  done
  python -m evaluation.process --gen results/gen/pope_tune.jsonl --ablation full_toolkit
  python -m evaluation.tune --proc results/proc/full_toolkit/pope_tune.jsonl --write results/tuned.yaml
  for s in random popular adversarial; do python -m evaluation.process --gen results/gen/pope_$s.jsonl --all-ablations; done
elif [ "$BENCH" = chair ]; then
  python -m evaluation.generate --input data/benchmarks/chair.jsonl --out results/gen/chair.jsonl --n 3 --max-new-tokens 128 --push-every 50
  python -m evaluation.process --gen results/gen/chair.jsonl --all-ablations
fi
python -m evaluation.hub_sync push --repo "$RESULTS_REPO" --patterns "results/gen/${BENCH}*" "results/proc/**/${BENCH}*" "results/cache/*${BENCH}*" "results/tuned.yaml"
```
The verification cache is written per benchmark, `results/cache/verification_<bench>.jsonl`, so the two processes never write the same file. The `smoke` branch is the same with `--limit 5` (POPE) and `--limit 3` (CHAIR). It also works on the Lenovo from Git Bash, as a fallback.
- `kaggle/run_benchmarks.ipynb`, one cell per block:
```python
# 1. secrets + clone (Kaggle: Add-ons -> Secrets; Settings: GPU T4 x2, Internet On)
import os, subprocess
from kaggle_secrets import UserSecretsClient
sec = UserSecretsClient()
os.environ["HF_TOKEN"] = sec.get_secret("HF_TOKEN")
os.environ["GH_TOKEN"] = sec.get_secret("GH_TOKEN")          # skip if the repo is public
os.environ["RESULTS_REPO"] = "Prithxvhie44/vlm-results"
!git clone --depth 1 https://$GH_TOKEN@github.com/<owner>/vlm_toolkit.git /kaggle/working/vlm
%cd /kaggle/working/vlm
!nvidia-smi --query-gpu=name,memory.total --format=csv        # expect 2 x Tesla T4

# 2. install (keeps Kaggle's CUDA torch) + pull partial results for resume
!pip install -q -r requirements.txt -r requirements-cuda.txt
!python -m evaluation.hub_sync pull --repo $RESULTS_REPO

# 3. data + weights ONCE, before the parallel processes start
!python -m evaluation.prepare_data --out data/benchmarks --images data/images --pope-images 450 --chair-images 500 --tune-images 50 --seed 42
from huggingface_hub import snapshot_download
for m in ["llava-hf/llava-1.5-7b-hf", "IDEA-Research/grounding-dino-tiny", "openai/clip-vit-base-patch32"]:
    snapshot_download(m)

# 4. POPE on GPU 0, CHAIR on GPU 1, in parallel
BENCHES = ["pope", "chair"]            # use ["smoke"] for checkpoint 1
procs = [subprocess.Popen(["bash", "jobs/run_eval.sh", b], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(i)},
                          stdout=open(f"/kaggle/working/{b}.log", "w"), stderr=subprocess.STDOUT)
         for i, b in enumerate(BENCHES)]
print([p.wait() for p in procs])       # 0 = success; read /kaggle/working/*.log otherwise
!tail -n 20 /kaggle/working/*.log
```
- **Checkpoint 1 (interactive):** open the notebook with "Edit", set `BENCHES=["smoke"]`, run all cells, and watch `nvidia-smi`. Confirm LLaVA fp16 fits on one T4; if not, set `hf_precision: 4bit` in `config.yaml`. **Stop the interactive session when done**, because it uses quota while idle.
- **Full run:** set `BENCHES=["pope","chair"]` → **Save Version → "Save & Run All (Commit)"**. Close the browser. Watch progress in the Kaggle "Versions" tab logs, and in the dataset repo, which gets pushes every 50–300 samples.
- `/kaggle/working` (results + logs) is also saved as the notebook version's **output**. That's a second copy if a Hub push fails.

**Test:** the smoke run finishes, its files appear in the dataset repo, and re-running the notebook skips the existing samples (the log says "skipping N done").
**Done when:** the smoke run passes at checkpoint 1 (H+3).

#### P3. FastAPI backend (P1, ~2 h; while the full Kaggle run is going)
**Files:** `api/server.py`, `database/db.py`, `scripts/dev.ps1`, `scripts/dev.sh`
- Port every route from `frontend_adapter.py` 1:1 (same JSON; reuse its validation). Add `/api/benchmarks` and `/api/review` (§3.6).
- `db.py`: an `annotations` table, `save_annotation()`, and `flagged_claims(limit)` (claims whose action is `ABSTAIN` in recent payloads). The audit payload gains `claim_actions`, `action_details`, `claim_values` and `selected`, because the paper says "action taken" is logged.
- `uvicorn api.server:app --host 127.0.0.1 --port 8010`. `scripts/dev.ps1` starts uvicorn and `pnpm dev` in two windows.

**Test:** `curl http://127.0.0.1:8010/health`. One dashboard analysis works and appears under Experiments. POST then GET `/api/review` round-trips.
**Done when:** the dashboard works unchanged on FastAPI and `frontend_adapter.py` is deleted.

#### P5. BLIP-2 POPE baseline (P2 stretch, after the full run succeeds)
Add `Blip2ForConditionalGeneration` (`Salesforce/blip2-opt-2.7b`, fp16 ~7.5 GB, fits on one T4) to `HFVLMEngine` (choose the class from the model id; BLIP-2 prompt `"Question: {q} Answer:"`). Add a `pope_blip2` branch to `run_eval.sh` that writes `results/gen/blip2/pope_*.jsonl`. Run it as a second Kaggle commit (~45 min, can use Kavyansh's quota). It gives the paper's second baseline (Table III POPE row).

#### P6. Integrator (continuous)
Merge only reviewed, green PRs (Git rules in §5). Never push to `main` yourself. Start, monitor and re-run the Kaggle commits, and check the remaining GPU quota in Kaggle Settings before each run. Post a status update in the group chat every ~2 h, with the Kaggle version number.

---

### HARSH: paper-faithful core (scoring, decisions, correction, process stage)

#### H1. Config + legacy cleanup + schema (P0, ~1 h; schema in the first 45 min)
- Push the §3.1 schema first.
- `config/config.yaml` is the single source of truth:
```yaml
vlm: {provider: gemini, hf_model: llava-hf/llava-1.5-7b-hf, hf_precision: fp16}
generation: {num_candidates: 3, temperature: 0.7, max_new_tokens: 128, seed: 42}
reliability: {lambda_verification: 0.6, lambda_probability: 0.2, lambda_agreement: 0.2, rerank_threshold: 0.5}
decision: {tau_lo: 0.30, tau_hi: 0.70}
verification: {grounding_model: IDEA-Research/grounding-dino-tiny, grounding_threshold: 0.30, detect_floor: 0.10,
               attribute_model: openai/clip-vit-base-patch32, attribute_threshold: 0.50, device: auto,
               local_files_only: false, cache_dir: results/cache}
```
- `load_config()` merges `results/tuned.yaml` if present. Remove the hard-coded `.80/.40` defaults everywhere.
- Delete `claims.py`, `correction.py`, `scoring.py` and `app.py`. Rewrite `tests/test_core.py` against the package APIs, and change `"VERIFIED"` → `"SUPPORTED"` in `tests/test_toolkit.py`.

**Test:** `pytest` green, and no `0.8`/`0.4` threshold literals remain in `core/` or `reliability/`.

#### H2. Eq. 3 exactly (P0, ~1 h)
**File:** `reliability/engine.py`
- **A_j** = the fraction of y_j's claims also asserted by **at least one of the other n−1** candidates. If n=1, set `agreement_available=False` and redistribute λ₃ (the same mechanism as for an unavailable p_j).
```python
def agreement(cands):
    keys = [{_key(c) for c in cand.claims} for cand in cands]
    for i, cand in enumerate(cands):
        others = [k for j, k in enumerate(keys) if j != i]
        cand.agreement_available = bool(others and keys[i])
        cand.agreement = round(sum(any(k in o for o in others) for k in keys[i]) / len(keys[i]), 3) if cand.agreement_available else 0.0
```
- mean_i(v_i) runs over claims whose verifier was available (`evidence_quality > 0`). v_i uses the consistent scores from K2. Fill `claim_values`. Move all decision logic out of `score()`.

**Test (`tests/test_policy.py`):**
- n=1 → `agreement_available False`
- a claim unique to one of 3 candidates → that candidate's A < 1
- λ = (.6, .2, .2), v=.9, p=.8, A=1 → **R = 0.90**
- p unavailable → its weight goes to verification

#### H3. Per-claim policy + paper rerank (P0, ~2 h)
**Files:** `core/policy.py`, `core/pipeline.py`
```python
def claim_action(v, ev, claim, cfg):
    if ev is None or ev.status == "AMBIGUOUS" or not ev.evidence_quality:  return "ABSTAIN"   # verifier unavailable
    if v >= cfg.hi:                                                         return "ACCEPT"
    if v <= cfg.lo:   # correct only with positive evidence (§IV-E.2)
        if claim.type == "object" and v < cfg.grounding_threshold:          return "CORRECT"   # no detection -> delete
        if claim.type == "attribute" and ev.verified_value:                 return "CORRECT"   # alternative on the same region
        if claim.type == "quantity" and ev.verified_value:                  return "CORRECT"
        return "ABSTAIN"
    return "ABSTAIN"                                                        # lo < v < hi -> flag for review
```
`process_candidates` does the following:
1. Verify, score and assign actions for **all** candidates, without sorting first.
2. Selection:
   - `orig = candidates[0]` (greedy). If `R_orig ≥ rerank_threshold`, keep orig.
   - Otherwise, if some candidate has `R ≥ rerank_threshold`, pick `argmax R` and set the decision to **RERANK**.
   - Otherwise keep orig and set the decision to **ABSTAIN** (no reliable candidate).
3. Decision for the chosen candidate, unless it's already RERANK or ABSTAIN: any claim CORRECT → **CORRECT**; else any ABSTAIN → **ABSTAIN** (flagged); else **ACCEPT**.
4. Apply corrections (H4) to the chosen candidate, set `selected=True`, and return it first, with the rest in their original order.
5. When `reliability=False`, always keep orig and skip the R-based abstain.

**Test (`tests/test_pipeline.py`, fake verifier, no models):**
- Table IV fixture → person ACCEPT, shirt CORRECT, jeans CORRECT, surfboard CORRECT/delete; the text becomes "A person in a red shirt and blue jeans stands on the beach."
- R_orig=.3 and R_2=.8 → RERANK, with candidate 2 first
- all R low → ABSTAIN
- v=.5 → the claim is ABSTAIN (flagged)

#### H4. Correction driven by claim actions (P1, ~1 h)
**File:** `correction/engine.py`
- Act only on claims whose action is `CORRECT`.
- **Swap:** if two contradicted attribute claims have mutually exchanged values (shirt blue→red, jeans red→blue), record `action_details = "swap:shirt<->jeans"`. Otherwise record `replace:<value>`.
- **Delete:** remove the whole noun phrase, including determiner, adjectives and attachment verb (`holding|carrying|with|and`). If the object is the sentence subject, drop the sentence. Never return empty text. Use `claims.vocab.surface_forms(cls)` so multi-word and plural forms are handled.

**Test:** 6–8 sentences. For example, "A man holding a red umbrella stands near a fire hydrant." with the hydrant deleted gives a grammatical result. The swap case is labelled `swap`.

#### H5. Ablation switches (P0, ~0.5 h)
`evaluation/ablations.py` maps each name to a `PipelineConfig` override (`base_vlm`, `full_toolkit`, `no_attribute_binding`, `no_reliability_scoring`, `n_equals_1`). `process_candidates` honours `verification`, `attribute_verifier`, `reliability` and `candidate_count`.
**Test:** the same fake input under each ablation behaves as expected (for example, no_attribute_binding leaves "blue shirt").

#### H6. Process stage (P0, ~1.5 h)
**File:** `evaluation/process.py`
```text
python -m evaluation.process --gen results/gen/chair.jsonl --ablation full_toolkit      # → results/proc/full_toolkit/chair.jsonl
python -m evaluation.process --gen results/gen/pope_random.jsonl --all-ablations
python -m evaluation.process --gen ... --cache-only     # laptop reprocessing: fail if a cache entry is missing, never load models
```
- Resumable. Writes the §3.5 proc record. Keeps first-pass latency when an earlier row exists.
- **POPE:** standard yes/no parse (lower-case; words contain `no` or `not` → no, else yes). If yes: `Claim(type="object", subject=to_class(obj) or obj)`, verify, `claim_action`, then apply §2.7. Store `v`, `p` and `abstained`. For `base_vlm`, final = base.
- **CHAIR:** `process_candidates(image, rec["candidates"], cfg)`. `final_text` is the selected candidate's corrected text; `base_text` is candidate 0's original text.

**Test:** run with `--fake-verifier` on a 5-row fixture in CI. Real run in the smoke job (checkpoint 2).

---

### YASH: vocabulary, datasets, CHAIR, metrics, tuning, report

#### Y1. COCO vocabulary + synonyms (P0, ~1 h)
**Files:** `claims/vocab.py`, `data/coco_synonyms.txt`
- Copy the CHAIR synonym list from the original CHAIR code (Rohrbach et al., GitHub `LisaAnne/Hallucination`, `data/synonyms.txt`; check the path). Each line is `class, syn1, syn2, ...` for the 80 COCO classes. Cite it in the paper.
- API: `COCO_CLASSES`, `to_class(phrase)`, `surface_forms(cls)` (longest first), and `find_objects(text) -> [(class, start, end)]` (longest match first, 2-word phrases before 1-word, no overlaps).
- Singularisation: a table of irregulars (men, women, children, people, mice, knives, geese), then `-ies→y`, `-es`/`-s` only when the result is in the vocab.
- Deduplicated `COLORS = ("red","blue","green","yellow","black","white","orange","brown","gray","purple","pink")`, with grey → gray as an alias. `MATERIALS = ("wooden","metal","plastic","glass","leather","stone","fabric","paper")`.

**Test:** `to_class("men")=="person"`; `find_objects("a hot dog next to a dog")` returns both, not overlapping; `bus` stays `bus`.

#### Y2. Extractor upgrade (P0, ~2.5 h)
**File:** `claims/extractor.py`
- Objects via `find_objects()` (all 80 COCO classes) plus `EXTRA_OBJECTS` (`shirt, jeans, pants, hat, jacket, dress`) so the Table IV demo still works.
- Attributes (colour and material):
  - `<attr> <obj>`
  - `<attr> and <attr> <obj>`
  - `<obj> (is|are) <attr>`
  - `<obj> that (is|are) <attr>`
  - one intervening adjective: `<attr> <adj> <obj>`
- Counts: words 1–10 and digits. Relations: all matches, limited to the same sentence. `Claim.text` = the sentence span the claim came from.

**Test:** "A woman in a blue shirt is sitting on a wooden bench next to two dogs. The bench is brown." should give:
- objects person, shirt, bench, dog
- attributes shirt:color:blue, bench:material:wooden, bench:color:brown
- quantity dog:2
- relation person next_to dog

Old tests must still pass.

#### Y3. Dataset preparation (P0, ~1.5 h; needed for checkpoint 1)
**File:** `evaluation/prepare_data.py`
```text
python -m evaluation.prepare_data --out data/benchmarks --images data/images --pope-images 450 --chair-images 500 --tune-images 50 --seed 42 [--only pope|chair|smoke]
```
- **POPE:** `datasets.load_dataset("lmms-lab/POPE", split="test")`, which has question, answer, category, image_source and image. Use seed 42 to pick 50 tune images (random split only) and up to 450 disjoint eval images. Keep all 6 questions per image per split, save images, and parse `object` from "Is there a X in the image?". Fallback: the POPE JSONs from GitHub `AoiDragon/POPE` plus images from `http://images.cocodataset.org/val2014/<file>`.
- **CHAIR:** `instances_val2014.json` from `http://images.cocodataset.org/annotations/annotations_trainval2014.zip`. Use the POPE eval images first, then top up from val2014 by URL to 500. Exclude the tune images. `gt_objects` = unique instance category names → `to_class`.
- It must run both inside the Kaggle notebook (Linux) and on a laptop (`--only smoke` = 2 POPE images + 5 CHAIR images, for development). Add `data/` to `.gitignore`.

**Test:**
- `pope_random.jsonl` = 6 × N lines
- `chair.jsonl` = N lines
- all image paths exist
- an assert that tune and eval image ids are disjoint

#### Y4. Metrics, latency, calibration, report (P0, ~2 h)
**Files:** `evaluation/chair.py`, `evaluation/evaluator.py`, `evaluation/metrics.py`, `evaluation/reports.py`, `evaluation/run_benchmarks.py`
- **CHAIR:** `mentioned = {cls for cls,_,_ in find_objects(text)}`.
  - CHAIR_S = share of captions with a hallucinated object
  - CHAIR_I = hallucinated mentions / all mentions
  - object recall = |mentioned ∩ gt| / |gt|
  - average caption length
- **POPE from proc rows:** Acc, P, R, F1 and yes-ratio per split (positive class = yes, computed directly), plus abstention rate and N.
- **Latency ratio** = mean(`total`) / mean(`generation_base`) per ablation, using values measured on the Kaggle T4 only. Report it honestly against the paper's < 2× target.
- **Calibration:** on POPE full_toolkit rows where the base answer was yes, R = λ₁v + λ₂p against "final answer correct". Report ECE and Brier using the existing `classification_metrics`.
```text
hf download Prithxvhie44/vlm-results --repo-type dataset --local-dir . --include "results/*"
python -m evaluation.run_benchmarks --proc results/proc --out results/benchmark_report.json --markdown results/RESULTS.md
```
- `RESULTS.md` tables:
  - **POPE:** rows base_vlm / full_toolkit (+ BLIP-2 base if run) × split; columns N, Acc, P, R, F1, Yes%, Abstain%
  - **CHAIR:** rows base_vlm, full_toolkit, n_equals_1, no_reliability_scoring, no_attribute_binding; columns N, CHAIR_S↓, CHAIR_I↓, Recall↑, Len, Latency×
  - a header with model, precision, hardware, seed, tuned thresholds, date, and the note "POPE N=450/split (50 held out)"

**Test:** hand-computed fixtures. ["a dog and a cat"] with gt {dog} → CHAIR_S 1.0, CHAIR_I 0.5, recall 1.0. A 4-row POPE fixture → known metrics.

#### Y5. Held-out tuning (P0, ~1 h; runs automatically inside the Kaggle POPE process)
**File:** `evaluation/tune.py --proc results/proc/full_toolkit/pope_tune.jsonl --write results/tuned.yaml`
- Grid lo ∈ {0.10…0.45}, hi ∈ {0.50…0.90}, lo < hi. Recompute final answers from the stored `v` and maximise **F1** (tie-break: lower abstention).
- Grid λ₁ ∈ {0, 0.1, …, 1} with λ₂ = 1−λ₁. Minimise the **ECE** of R.
- Write `results/tuned.yaml` (`decision.tau_lo/tau_hi`, `reliability.lambda_*`). `load_config` picks it up automatically. λ₃ stays at its default; say so in the paper.

**Test:** a synthetic file where every label-false row has v < 0.2 → tuned lo ≥ 0.2.

#### Y6. Optional LLM claim extractor (P2)
`claims/llm_extractor.py` uses the `hf-router` or Gemini provider and returns JSON tuples (object, attribute_type, attribute_value, relation, relation_target). They're normalised with `to_class` and merged with the rule claims. Gated by `claims.use_llm: false`. It's **demo only** and off for benchmarks (determinism, cost). This is the paper's "rule-and-LLM" extractor.

#### Y7. SugarCrepe attribute subsets (P2 stretch, together with Harsh, only if everything else is done)
Run `replace-att` and `swap-att` only (data from GitHub `RAIVNLab/sugar-crepe` + COCO val2017 images). For each image, score the positive and negative captions with the caption-level reliability R (extract → verify → R, no generation; §V-B adaptation). The model is correct if R(pos) > R(neg). This is CPU/MPS-feasible from cache after one verification pass, or a short Kaggle run. It's the only quantitative evidence for the attribute-binding contribution.

---

### KAVYANSH: verification layer, dashboard, demo

#### K1. Device, speed, API drift, verification cache (P0, ~1.5 h; needed for checkpoint 1)
**Files:** `utils.py`, `verification/grounding.py`, `verification/attribute_verifier.py`, `verification/service.py`
- `utils.get_device(pref="auto") -> "cuda"|"mps"|"cpu"`. Move models and inputs `.to(device)`. Config `verification.device` overrides it.
- Wrap inference in `torch.no_grad()` (it's missing in `GroundingDINO.detect`).
- transformers API drift:
```python
try:
    res = proc.post_process_grounded_object_detection(outputs, inputs.input_ids, threshold=floor, text_threshold=floor, target_sizes=ts)[0]
except TypeError:
    res = proc.post_process_grounded_object_detection(outputs, inputs.input_ids, box_threshold=floor, text_threshold=floor, target_sizes=ts)[0]
```
- Detect at `detect_floor` (0.10) so s_obj is real below the threshold. SUPPORTED/UNSUPPORTED is still decided at `grounding_threshold`.
- **Disk cache** (§3.5) for grounding **and** CLIP probabilities, one file per benchmark (`verification_<bench>.jsonl`, chosen via an env var or argument). `--cache-only` mode raises on a miss instead of loading models.

**Test:** `tests/test_verification.py`. Both kwarg paths work with a fake processor, and the second call hits the cache with no model call. Then a real run on the Mac with one image prints device `mps`.

#### K2. Verifier correctness (P0, ~1.5 h)
- Use Yash's deduplicated `COLORS`. This fixes the `COLORS[:-1]` bug (pink unreachable, gray/grey split).
- Prompt `f"a photo of a {label} {object_name}"` instead of `"a {label} object"`.
- **Material** (P1): crop-level Eq. 2 with `MATERIALS` and `f"a photo of a {object_name} made of {material}"`.
- **Count:** NMS at IoU > 0.5 over boxes ≥ threshold; `verified_value` = count; v = s_obj if it matches, else 0.
- **Relation:** v = min(s_subj, s_obj) if the geometry holds, else 0 (no more `1 − score`).

**Test:** fakes. {pink: .9} on a "blue" claim → CONTRADICTED with pink. 3 overlapping boxes + 1 separate → count 2. A contradicted relation gives v = 0.

#### K3. Dashboard, demo-ready (P0, ~3 h)
- `lib/types.ts`: the §3.1 fields.
- **Claims/Evidence:** a Table IV-style table (*Claim · Verification result: v, explanation, crop · Action + detail*) and an original-vs-corrected diff (strike-through deletions, highlighted replacements).
- **Candidates:** p_j ("token confidence") or "n/a (API model)"; agreement or "n/a (n=1)"; a badge on the `selected` candidate with the RERANK reason.
- **Review section:** add `review` to `app/[section]/page.tsx` and the header. List `/api/review` items with crop, claim, v and explanation, Correct/Incorrect/Unsure buttons and a note field → POST.
- **Evaluation:** render the POPE and CHAIR tables from `/api/benchmarks` (same columns as `RESULTS.md`).
- `next.config.ts`: add rewrites for `/api/benchmarks` and `/api/review`. Show `hf-local` and `hf-router` in the provider dropdown.

**Test:** `corepack pnpm build` is clean. Manual: the paper fixture through manual candidates (`|||`) shows 4 actions + the diff. A review label persists after reload.

#### K4. Demo assets, script, README (P0, ~1.5 h)
- `test_images/`: 4–5 images you have rights to (take photos if needed):
  - red shirt / blue jeans (Table IV)
  - a street scene for deletion
  - an ambiguous small object (ABSTAIN → Review)
  - two dogs (count)
- `demo/DEMO.md`: a 5-minute script covering Table IV live (Gemini), a rerank example, the review queue, the evaluation page, and how the benchmarks were produced (Kaggle notebook → HF dataset repo). **Offline fallback:** `python demo_paper_example.py` plus screenshots in `demo/screens/`.
- `README.md`: Windows (PowerShell) and macOS setup, the Kaggle workflow (`kaggle/run_benchmarks.ipynb`), result download, and an updated status table.
- The Mac is the demo machine: keep the verifier weights cached and `local_files_only: true` after the first run.

---

## 8. End-to-end test checklist (Phase 2 smoke, then again before freeze)

| # | Check | Command / action | Pass criterion |
|---|---|---|---|
| 1 | Unit tests | `python -m pytest -q` on all laptops | green, no GPU |
| 2 | Paper fixture | `python demo_paper_example.py` | "A person in a red shirt and blue jeans stands on the beach."; actions ACCEPT/CORRECT/CORRECT/CORRECT(delete) |
| 3 | Local data | `python -m evaluation.prepare_data ... --only smoke` | files + images; ids disjoint |
| 4 | Kaggle smoke | notebook with `BENCHES=["smoke"]` (interactive) | finishes; gen + proc + cache files in the dataset repo; peak VRAM < 15 GB per T4 |
| 5 | Resume | re-run the notebook | logs show skipped samples; no duplicates |
| 6 | Laptop reprocess | `hf download ...` then `python -m evaluation.process --gen results/gen/smoke_chair.jsonl --all-ablations --cache-only` | runs without loading models |
| 7 | Report | `python -m evaluation.run_benchmarks ...` | `RESULTS.md` tables with N |
| 8 | Live demo (Mac) | dashboard + Gemini/hf-router + Table IV image | claims table, boxes, crops, corrected text; saved in Experiments |
| 9 | Review queue | label a flagged claim, reload | persisted |
| 10 | Evaluation page | `/evaluation` | POPE + CHAIR tables |

---

## 9. Paper-faithfulness checklist (tick before freeze)

- [ ] Eq. 1 s_obj = max d_b (score available below the threshold via the detect floor)
- [ ] Eq. 2 s_attr = max d_b·P(a|crop_b) for colour **and** material on the object's crop
- [ ] Eq. 3 with real p_j (hf-local) and A_j over the other n−1 candidates; unavailable terms redistributed and logged
- [ ] Per-claim accept/correct/abstain with lo/hi; rerank only when the top candidate is below threshold and another passes
- [ ] Replace/swap for binding errors; delete hallucinated objects; verified content untouched
- [ ] Audit log: image hash, candidate history, claim scores, **action taken**
- [ ] Real sampled n-best; candidate 1 = greedy baseline
- [ ] POPE Acc/P/R/F1/yes-ratio × 3 splits; CHAIR_S, CHAIR_I **and object recall**
- [ ] All 4 ablations + base; latency ratio, abstention rate, ECE of R
- [ ] lo/hi and λ tuned on a **held-out** split disjoint from eval
- [ ] FastAPI + Next.js dashboard with original vs corrected, per-claim scores, flagged-case annotation
- [ ] RESULTS.md states the model, precision (fp16, or 4-bit if the fallback was used), the Kaggle T4 GPU, N (POPE 450/split, CHAIR 500) and the caveat that binding isn't measured by POPE/CHAIR

---

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| No GPU / no Internet option in Kaggle | The account isn't phone-verified. Do it at H+0, for both Prithvi and Kavyansh |
| GPU T4 x2 queued or unavailable | Use Kavyansh's account, or run POPE and CHAIR as two single-GPU commits (one per account). Last resort: Lenovo with `run_eval.sh` + `hf_precision: 4bit`, smaller N |
| LLaVA-7B fp16 OOM on a 15 GB T4 | `vlm.hf_precision: 4bit` (decide at checkpoint 1) and report it |
| Session dies or hits the 12 h limit | Pushes happen every 50–300 samples. Re-run the notebook and it resumes. The full run is ~4 h, well under 12 h |
| Weekly quota runs low | The full run needs ~4–5 of ~30 h. Stop interactive sessions when idle; use the second account for stretch runs |
| Two processes push at the same moment | `hub_sync.push` retries with backoff, and `/kaggle/working` output is a second copy |
| Private GitHub repo can't be cloned | Add the `GH_TOKEN` Kaggle secret, or upload the code as a private Kaggle dataset and copy it in |
| `lmms-lab/POPE` load fails | Fallback to the POPE GitHub JSONs + COCO URLs (Y3) |
| Gemini free-tier rate limit during the demo | 1 candidate in the demo, pre-run screenshots, and the offline `demo_paper_example.py` |
| MPS op missing on the Mac | `PYTORCH_ENABLE_MPS_FALLBACK=1`, or `verification.device: cpu`. The demo only verifies a single image |
| Results don't beat the baseline | Report honestly (the paper claims no figures in advance). Discuss per-split behaviour, abstention, recall and detector limits (§VII) |
| Merge conflicts | File ownership (§4), small PRs, pull at each checkpoint |

---

**Sources for platform limits used here:** [Free cloud GPUs in 2026 (Kaggle 12 h session, ~30 h/week)](https://gpuperhour.com/blog/free-cloud-gpus-and-credits) · [kgz (Kaggle limits summary)](https://pypi.org/p/kgz) · [HF pricing](https://huggingface.co/pricing) · [Inference Providers](https://huggingface.co/docs/inference-providers/index). Kaggle's weekly quota floats, so check Kaggle → Settings for the current value.
