"""Black-box VLM execution abstraction and reproducible repeated sampling."""
from __future__ import annotations
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

    def generate(self, image_path: str, query: str, **kwargs) -> dict:
        return generate_vlm_response(image_path, query, self.provider)

    def get_token_confidence(self, response: dict) -> float | None:
        value = response.get("probability")
        return float(value) if response.get("probability_available") and value is not None else None

    def generate_candidates(self, image_path: str, query: str, n: int, **kwargs) -> list[dict]:
        # Provider adapters do not expose native n-best logits. These are
        # repeated controlled generations, explicitly labelled as such.
        results = []
        for index in range(n):
            item = self.generate(image_path, query + f"\nCandidate sample {index + 1} of {n}.")
            item["generation_strategy"] = "repeated_controlled_generation_not_native_nbest"
            results.append(item)
        return results
