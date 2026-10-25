"""FastAPI service for the dashboard (paper Sec. V-D).

Run: uvicorn api.server:app --host 127.0.0.1 --port 8010
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from claims.graph import graph_data
from core.config import ROOT, load_config, raw_config
from core.pipeline import run
from database import db
from evaluation.metrics import classification_metrics
from vlm import provider_models, providers

MAX_IMAGE_BYTES = 15 * 1024 * 1024
REPORT = ROOT / "results" / "benchmark_report.json"

app = FastAPI(title="VLM Reliability Toolkit", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])


class AnalyzeRequest(BaseModel):
    image_base64: str
    filename: str = "upload.png"
    query: str = Field("Describe the objects and their colors.", max_length=2000)
    candidate_count: int = Field(3, ge=1, le=3)
    provider: str
    manual_response: str = Field("", max_length=12000)
    weights: dict[str, float] = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    experiment_id: int
    claim_id: str
    label: str = Field(pattern="^(correct|incorrect|unsure)$")
    note: str = Field("", max_length=2000)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict:
    options, cfg, settings = providers(), load_config(), raw_config()
    default = settings.get("vlm", {}).get("provider")
    return {"providers": options, "models": provider_models(),
            "provider": default if default in options else (options[0] if options else ""),
            "defaults": {"candidate_count": cfg.candidate_count,
                         "verification_weight": cfg.weights["verification"], "agreement_weight": cfg.weights["agreement"],
                         "probability_weight": cfg.weights["probability"], "rerank_threshold": cfg.rerank_threshold,
                         "high_threshold": cfg.hi, "low_threshold": cfg.lo,
                         "thresholds": {kind: {"lo": lo, "hi": hi} for kind, (lo, hi) in cfg.thresholds.items()},
                         "tuned": (ROOT / "results" / "tuned.yaml").exists()}}


@app.get("/api/evaluation")
def evaluation() -> dict:
    return classification_metrics([])


@app.get("/api/benchmarks")
def benchmarks() -> dict:
    if not REPORT.exists():
        return {"status": "NOT RUN", "message": "No benchmark report yet. Run evaluation.run_benchmarks after the Kaggle run."}
    return json.loads(REPORT.read_text())


@app.get("/api/history")
def history() -> list[dict]:
    return [{"id": row[0], "created_at": row[1], "query": row[2]} for row in db.recent(100)]


@app.get("/api/history/{item_id}")
def history_item(item_id: int) -> dict:
    row = db.get(item_id)
    if not row:
        raise HTTPException(404, "Experiment not found")
    return {"id": row[0], "created_at": row[1], "query": row[2], "payload": json.loads(row[3])}


@app.get("/api/review")
def review_queue() -> list[dict]:
    return db.flagged_claims()


@app.post("/api/review")
def review(item: ReviewRequest) -> dict:
    if not db.get(item.experiment_id):
        raise HTTPException(404, "Experiment not found")
    db.save_annotation(item.experiment_id, item.claim_id, item.label, item.note)
    return {"status": "saved"}


@app.post("/api/analyze")
def analyze(body: AnalyzeRequest) -> dict:  # sync: FastAPI runs it in a worker thread
    try:
        image_bytes = base64.b64decode(body.image_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "Image data is not valid base64") from exc
    if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Image is empty or exceeds the 15 MB limit")
    if body.provider not in providers():
        raise HTTPException(400, "Select a configured generator VLM provider")
    suffix = Path(Path(body.filename).name).suffix.lower()
    suffix = suffix if suffix in {".png", ".jpg", ".jpeg", ".webp"} else ".png"
    cfg = load_config()
    weights = dict(cfg.weights)
    for name in ("verification", "agreement", "probability"):
        if name in body.weights:
            weights[name] = min(1.0, max(0.0, float(body.weights[name])))
    cfg = cfg.with_overrides(weights=weights, candidate_count=body.candidate_count)

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp.write(image_bytes)
        image_path = temp.name
    try:
        candidates, error = run(image_path, body.query, body.provider, cfg, body.manual_response)
    except Exception as exc:  # transport boundary: report, keep serving
        raise HTTPException(502, f"Verification request failed: {type(exc).__name__}: {str(exc)[:300]}") from exc
    finally:
        Path(image_path).unlink(missing_ok=True)
    if not candidates:
        raise HTTPException(502, error or "The generator returned no candidate text")

    exported = [candidate.export() for candidate in candidates]
    image_id = hashlib.sha256(image_bytes).hexdigest()
    configuration = {"generator_provider": body.provider, "visual_verifier": "Grounding DINO + region-level CLIP probe",
                     "candidate_count": body.candidate_count, "weights": weights, "rerank_threshold": cfg.rerank_threshold,
                     "thresholds": {k: list(v) for k, v in cfg.thresholds.items()}, "global_thresholds": [cfg.lo, cfg.hi]}
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "image_hash": image_id, "query": body.query,
               "model": [c.model for c in candidates], "configuration": configuration, "candidates": exported,
               "claims": [claim for c in exported for claim in c["claims"]],
               "verification_results": [ev for c in exported for ev in c["evidence"]],
               "reliability_scores": {c.id: c.reliability for c in candidates},
               "claim_actions": {c.id: c.claim_actions for c in candidates},
               "action_details": {c.id: c.action_details for c in candidates},
               "selected_candidate": candidates[0].id,
               "decision": [c.decision for c in candidates],
               "corrected_response": [c.corrected_text for c in candidates],
               "latency_ms": {c.id: c.stage_latency_ms for c in candidates}}
    experiment_id = db.save(body.query, payload)
    response_candidates = [{**data, "graph": graph_data(candidate.claims)} for candidate, data in zip(candidates, exported)]
    return {"experiment_id": experiment_id,
            "analysis": {"query": body.query, "image_id": image_id, "experiment_id": experiment_id, "candidates": response_candidates},
            "warning": error}
