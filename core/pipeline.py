from __future__ import annotations
from time import perf_counter
from claims.extractor import extract
from correction.engine import correct
from core.schemas import Candidate
from reliability.engine import agreement, score
from verification.service import verify
from vlm import generate_vlm_response

def run(image_path: str, query: str, candidate_count: int, weights: dict[str, float], manual_text: str = "", high: float = .80, low: float = .40, provider: str = "openai", verifier_provider: str | None = None) -> tuple[list[Candidate], str | None]:
    manual = [x.strip() for x in manual_text.split("|||") if x.strip()]
    verifier_provider = verifier_provider or provider
    candidates, error = [], None
    for index in range(candidate_count):
        started = perf_counter()
        model_probability, model_probability_available = None, False
        if manual:
            text, model = manual[index % len(manual)], "manual candidate"
        else:
            prompt = query + f"\nGenerate candidate {index+1}: concise, literal visual description; avoid speculation."
            generated = generate_vlm_response(image_path, prompt, provider)
            text, model, error = generated.get("response", ""), generated.get("model", ""), generated.get("error")
            model_probability = generated.get("probability")
            model_probability_available = bool(generated.get("probability_available") and model_probability is not None)
            if not text: break
        candidate = Candidate(f"candidate-{index+1}", text, model, claims=extract(text),
                              generator_provider=provider, verifier_provider=verifier_provider,
                              probability=model_probability, probability_available=model_probability_available)
        candidate.evidence = verify(image_path, candidate.claims, verifier_provider)
        if candidate.evidence:
            signal = candidate.evidence[0].signals.get("vlm_verification", {})
            candidate.verifier_model = str(signal.get("model", ""))
        candidates.append(candidate)
        candidate.latency_ms = round((perf_counter() - started) * 1000)
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
