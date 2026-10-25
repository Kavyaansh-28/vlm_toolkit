"""Black-box / white-box VLM execution abstraction (paper Sec. IV-A).

``hf-local`` runs a Hugging Face VLM on this machine and exposes real n-best
sampling plus token probabilities.  API providers cannot return native n-best
lists, so their candidates are repeated calls and are labelled as such.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Protocol

from vlm import generate_vlm_response


class VLMEngine(Protocol):
    def generate(self, image_path: str, query: str, **kwargs) -> dict: ...
    def generate_candidates(self, image_path: str, query: str, n: int, **kwargs) -> list[dict]: ...
    def get_token_confidence(self, response: dict) -> float | None: ...


@dataclass
class ProviderVLMEngine:
    provider: str
    temperature: float = .7

    def generate(self, image_path: str, query: str, **kwargs) -> dict:
        return generate_vlm_response(image_path, query, self.provider, temperature=kwargs.get("temperature"))

    def get_token_confidence(self, response: dict) -> float | None:
        value = response.get("probability")
        return float(value) if response.get("probability_available") and value is not None else None

    def generate_candidates(self, image_path: str, query: str, n: int, **kwargs) -> list[dict]:
        # Candidate 1 uses temperature 0 (closest to greedy); the rest are sampled.
        # The calls are independent, so they run concurrently; results keep candidate order.
        temperatures = [0.0] + [kwargs.get("temperature", self.temperature)] * (n - 1)
        with ThreadPoolExecutor(max_workers=max(1, n)) as pool:
            results = list(pool.map(lambda t: self.generate(image_path, query, temperature=t), temperatures[:n]))
        for item in results:
            item["generation_strategy"] = "repeated_api_calls"
        return results


def get_engine(provider: str) -> VLMEngine:
    if provider == "hf-local":
        from core.config import raw_config
        from models.hf_vlm import load_engine
        options = raw_config().get("vlm", {})
        return load_engine(str(options.get("hf_model", "llava-hf/llava-1.5-7b-hf")), str(options.get("hf_precision", "fp16")))
    return ProviderVLMEngine(provider)
