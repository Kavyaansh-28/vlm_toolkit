"""Typed records used by the research-toolkit pipeline."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ClaimType = Literal["object", "attribute", "relation", "quantity"]

@dataclass
class Claim:
    id: str
    type: ClaimType
    subject: str
    value: str | int | None = None
    attribute: str | None = None
    object: str | None = None
    text: str = ""
    # Optional instance selector; None means class-level and must stay uncertain
    # when several instances cannot be disambiguated from the language.
    instance_id: str | None = None

@dataclass
class Evidence:
    claim_id: str
    status: str
    score: float
    source: list[str]
    confidence: float = 0.0
    boxes: list[list[float]] = field(default_factory=list)
    verified_value: str | int | None = None
    explanation: str = ""
    # `status` is one of SUPPORTED/CONTRADICTED/UNSUPPORTED/AMBIGUOUS.
    evidence_quality: float | None = None
    signals: dict[str, Any] = field(default_factory=dict)
    diagnosis: str | None = None
    binding_status: str | None = None
    instance_ids: list[str] = field(default_factory=list)

@dataclass
class Candidate:
    id: str
    text: str
    model: str
    claims: list[Claim] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    agreement: float = 0.0
    reliability: float = 0.0
    decision: str = "ABSTAIN"
    corrected_text: str = ""
    diagnosis: list[str] = field(default_factory=list)
    probability: float | None = None
    probability_available: bool = False
    claim_reliability: dict[str, float] = field(default_factory=dict)
    generator_provider: str = ""
    verifier_provider: str = ""
    verifier_model: str = ""
    latency_ms: int | None = None

    def export(self) -> dict[str, Any]:
        return {**asdict(self), "original_response": self.text,
                "claims": [asdict(x) for x in self.claims], "evidence": [asdict(x) for x in self.evidence]}
