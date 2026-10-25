from __future__ import annotations
from time import perf_counter
from claims.extractor import extract
from correction.engine import correct
from core.schemas import Candidate
from reliability.engine import agreement, score
from verification.service import verify
from vlm import generate_vlm_response
from vlm_engine import ProviderVLMEngine

def run(image_path: str, query: str, candidate_count: int, weights: dict[str, float], manual_text: str = "", high: float = .80, low: float = .40, provider: str = "openai") -> tuple[list[Candidate], str | None]:
    manual = [x.strip() for x in manual_text.split("|||") if x.strip()]
    candidates, error = [], None
    engine = ProviderVLMEngine(provider)
    generated_rows = [] if manual else engine.generate_candidates(image_path, query, candidate_count)
    for index in range(candidate_count):
        started = perf_counter()
        model_probability, model_probability_available = None, False
        if manual:
            text, model = manual[index % len(manual)], "manual candidate"
        else:
            generated = generated_rows[index]
            text, model, error = generated.get("response", ""), generated.get("model", ""), generated.get("error")
            model_probability = generated.get("probability")
            model_probability_available = bool(generated.get("probability_available") and model_probability is not None)
            if not text: break
        candidate = Candidate(f"candidate-{index+1}", text, model, claims=extract(text),
                              generator_provider=provider, verifier_provider="Grounding DINO + CLIP region probe",
                              probability=model_probability, probability_available=model_probability_available)
        candidate.generation_strategy = "manual_override" if manual else generated.get("generation_strategy", "repeated_controlled_generation_not_native_nbest")
        verification_started = perf_counter()
        candidate.evidence = verify(image_path, candidate.claims)
        candidate.stage_latency_ms["verification"] = round((perf_counter() - verification_started) * 1000)
        if candidate.evidence:
            candidate.verifier_model = "Grounding DINO + CLIP region probe"
        candidates.append(candidate)
        candidate.latency_ms = round((perf_counter() - started) * 1000)
        candidate.stage_latency_ms["total"] = candidate.latency_ms
    original_id = candidates[0].id if candidates else None
    agreement(candidates)
    for candidate in candidates:
        score(candidate, weights, high, low); correct(candidate)
    # Prefer a materially stronger candidate instead of blindly preserving candidate 1.
    candidates.sort(key=lambda item: item.reliability, reverse=True)
    # Reranking is only a selection action after the winner independently passed
    # the accept policy; it must not erase ambiguity/contradiction abstentions.
    if (len(candidates) > 1 and candidates[0].id != original_id and
            candidates[0].decision == "ACCEPT" and
            candidates[0].reliability - next((c.reliability for c in candidates if c.id == original_id), 0.0) >= .15):
        candidates[0].decision = "RERANK"
    return candidates, error
