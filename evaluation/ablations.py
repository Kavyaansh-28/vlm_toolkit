"""Named experiment configurations for the paper baseline and ablations (Sec. V-C)."""
from __future__ import annotations

from core.config import PipelineConfig

ABLATIONS = {
    "base_vlm": {"verification": False, "attribute_verifier": False, "candidate_count": 1, "reliability": False},
    "full_toolkit": {"verification": True, "attribute_verifier": True, "candidate_count": 3, "reliability": True},
    "no_attribute_binding": {"verification": True, "attribute_verifier": False, "candidate_count": 3, "reliability": True},
    "no_reliability_scoring": {"verification": True, "attribute_verifier": True, "candidate_count": 3, "reliability": False},
    "n_equals_1": {"verification": True, "attribute_verifier": True, "candidate_count": 1, "reliability": True},
}


def ablation_config(name: str, base: PipelineConfig) -> PipelineConfig:
    if name not in ABLATIONS:
        raise ValueError(f"Unknown ablation '{name}'. Choose from {', '.join(ABLATIONS)}.")
    return base.with_overrides(**ABLATIONS[name])
