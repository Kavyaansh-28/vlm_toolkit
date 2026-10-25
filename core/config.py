"""Configuration loading: config/config.yaml merged with results/tuned.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in (override or {}).items():
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def raw_config(path: str | Path | None = None, tuned: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else ROOT / "config" / "config.yaml"
    tuned = Path(tuned) if tuned else ROOT / "results" / "tuned.yaml"
    config = yaml.safe_load(path.read_text()) if path.exists() else {}
    if tuned.exists():
        config = _merge(config, yaml.safe_load(tuned.read_text()) or {})
    return config or {}


@dataclass
class PipelineConfig:
    lo: float = .30
    hi: float = .70
    rerank_threshold: float = .5
    weights: dict[str, float] = field(default_factory=lambda: {"verification": .6, "probability": .2, "agreement": .2})
    grounding_threshold: float = .30
    thresholds: dict[str, tuple[float, float]] = field(default_factory=dict)
    verification: bool = True
    attribute_verifier: bool = True
    reliability: bool = True
    candidate_count: int = 3
    temperature: float = .7
    max_new_tokens: int = 128
    seed: int = 42
    tuned_from: str | None = None  # path of the tuned.yaml merged in, if any

    def provenance(self) -> dict:
        """Settings that determine a processed result; stored with every benchmark row."""
        return {"thresholds": {k: list(v) for k, v in sorted(self.thresholds.items())}, "global_thresholds": [self.lo, self.hi],
                "weights": dict(sorted(self.weights.items())), "rerank_threshold": self.rerank_threshold,
                "grounding_threshold": self.grounding_threshold, "tuned": self.tuned_from is not None}

    def bounds(self, claim_type: str) -> tuple[float, float]:
        """(lo, hi) for a claim type; falls back to the global thresholds."""
        return self.thresholds.get(claim_type, (self.lo, self.hi))

    def with_overrides(self, **changes) -> "PipelineConfig":
        return replace(self, **changes)


def load_config(path: str | Path | None = None, tuned: str | Path | None = None) -> PipelineConfig:
    config = raw_config(path, tuned)
    tuned_path = Path(tuned) if tuned else ROOT / "results" / "tuned.yaml"
    reliability, decision, generation = config.get("reliability", {}), config.get("decision", {}), config.get("generation", {})
    lo, hi = float(decision.get("tau_lo", .30)), float(decision.get("tau_hi", .70))
    thresholds = {kind: (float(value.get("tau_lo", lo)), float(value.get("tau_hi", hi)))
                  for kind, value in (decision.get("per_type") or {}).items()}
    return PipelineConfig(
        lo=lo, hi=hi, thresholds=thresholds,
        rerank_threshold=float(reliability.get("rerank_threshold", .5)),
        weights={"verification": float(reliability.get("lambda_verification", .6)),
                 "probability": float(reliability.get("lambda_probability", .2)),
                 "agreement": float(reliability.get("lambda_agreement", .2))},
        grounding_threshold=float(config.get("verification", {}).get("grounding_threshold", .30)),
        candidate_count=int(generation.get("num_candidates", 3)),
        temperature=float(generation.get("temperature", .7)),
        max_new_tokens=int(generation.get("max_new_tokens", 128)),
        seed=int(generation.get("seed", 42)),
        tuned_from=str(tuned_path) if tuned_path.exists() else None,
    )
