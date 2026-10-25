"""Inference-time pipeline: candidates -> claims -> verification -> R_j -> policy -> correction."""
from __future__ import annotations

from time import perf_counter

from claims.extractor import extract
from core.config import PipelineConfig, load_config
from core.policy import assign_actions, select
from core.schemas import Candidate
from correction.engine import correct
from reliability.engine import agreement, score

VERIFIER_NAME = "Grounding DINO + CLIP region probe"

__all__ = ["PipelineConfig", "load_config", "process_candidates", "run", "rows_from_manual"]


def _candidate(index: int, row: dict, provider: str) -> Candidate:
    probability = row.get("probability")
    return Candidate(
        f"candidate-{index + 1}", row.get("response", row.get("text", "")) or "", row.get("model", ""),
        generator_provider=provider, verifier_provider=VERIFIER_NAME,
        probability=probability, probability_available=bool(row.get("probability_available", probability is not None) and probability is not None),
        num_tokens=row.get("num_tokens"), latency_ms=row.get("latency_ms"),
        generation_strategy=row.get("generation_strategy", row.get("strategy", "")))


def process_candidates(image_path: str, rows: list[dict], cfg: PipelineConfig, provider: str = "",
                       verify_fn=None) -> list[Candidate]:
    """Score and correct generated candidates; the SELECTED candidate is returned first.

    ``rows`` follow the VLM-engine contract (``response``/``probability``/...).
    ``verify_fn(image_path, claims, attribute=bool)`` defaults to the visual verifier.
    """
    if verify_fn is None:
        from verification.service import verify as verify_fn
    rows = [row for row in rows[:max(1, cfg.candidate_count)] if (row.get("response") or row.get("text"))]
    candidates = []
    for index, row in enumerate(rows):
        candidate = _candidate(index, row, provider)
        candidate.claims = extract(candidate.text)
        if cfg.verification:
            started = perf_counter()
            candidate.evidence = verify_fn(image_path, candidate.claims, attribute=cfg.attribute_verifier)
            candidate.stage_latency_ms["verification"] = round((perf_counter() - started) * 1000)
            candidate.verifier_model = VERIFIER_NAME
        candidates.append(candidate)
    if not candidates:
        return []

    if not cfg.verification:  # base-VLM baseline: the uncorrected greedy response
        for candidate in candidates:
            candidate.corrected_text, candidate.decision = candidate.text, "ACCEPT"
            candidate.decision_reason = "Verification disabled (uncorrected baseline)."
        candidates[0].selected = True
        return candidates

    agreement(candidates)
    for candidate in candidates:
        score(candidate, cfg)
        assign_actions(candidate, cfg)
    chosen, decision, reason = select(candidates, cfg)
    for index, candidate in enumerate(candidates):
        correct(candidate)
        if index != chosen:
            # Non-selected candidates keep their own policy outcome for inspection.
            _, own, own_reason = select([candidate], cfg.with_overrides(reliability=False))
            candidate.decision, candidate.decision_reason = own, own_reason
    selected = candidates[chosen]
    selected.selected, selected.decision, selected.decision_reason = True, decision, reason
    return [selected] + [c for i, c in enumerate(candidates) if i != chosen]


def rows_from_manual(manual_text: str) -> list[dict]:
    return [{"response": part.strip(), "model": "manual candidate", "generation_strategy": "manual_override"}
            for part in manual_text.split("|||") if part.strip()]


def run(image_path: str, query: str, provider: str, cfg: PipelineConfig | None = None,
        manual_text: str = "") -> tuple[list[Candidate], str | None]:
    """Live path used by the API: generate candidates, then process them."""
    cfg = cfg or load_config()
    error = None
    started = perf_counter()
    if manual_text.strip():
        rows = rows_from_manual(manual_text)
    else:
        from vlm_engine import get_engine
        rows = get_engine(provider).generate_candidates(image_path, query, cfg.candidate_count)
        error = next((row.get("error") for row in rows if row.get("error")), None)
    generation_ms = round((perf_counter() - started) * 1000)
    candidates = process_candidates(image_path, rows, cfg, provider)
    for candidate in candidates:
        candidate.stage_latency_ms["generation_total"] = generation_ms
        candidate.stage_latency_ms["total"] = generation_ms + candidate.stage_latency_ms.get("verification", 0)
    return candidates, error
