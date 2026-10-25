"""Region-level attribute checks for attribute-binding claims.

The probe only receives a crop from a grounded object box.  It therefore
cannot validate ``blue car`` merely because blue occurs elsewhere in the image.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from claims.vocab import COLORS, MATERIALS
from verification.cache import VerificationCache, add_cost, image_sha256

LABELS = {"color": list(COLORS), "material": list(MATERIALS)}
MATERIAL_NOUN = {"wooden": "wood", "metal": "metal", "plastic": "plastic", "glass": "glass",
                 "leather": "leather", "stone": "stone", "fabric": "fabric", "paper": "paper"}
MAX_BOXES = 5


def prompts_for(attribute_type: str, labels: list[str], object_name: str = "") -> list[str]:
    subject = object_name or "object"
    if attribute_type == "material":
        return [f"a photo of a {subject} made of {MATERIAL_NOUN.get(label, label)}" for label in labels]
    return [f"a photo of a {label} {subject}" for label in labels]


@dataclass
class AttributeProbeResult:
    probabilities: dict[str, float]
    available: bool = True
    reason: str = ""
    backend: str = "clip-region-probe"


class AttributeProbe(Protocol):
    def classify(self, crop, attribute_type: str, labels: list[str], object_name: str = "") -> AttributeProbeResult: ...


class CLIPRegionProbe:
    def __init__(self, model_id: str = "openai/clip-vit-base-patch32", local_files_only: bool = False, device: str = "auto"):
        self.model_id, self.local_files_only, self.device = model_id, local_files_only, device
        self._processor = self._model = None
        self._load_error: str | None = None

    def _load(self) -> bool:
        if self._processor is not None: return True
        if self._load_error: return False
        try:
            from transformers import CLIPModel, CLIPProcessor
            from utils import get_device
            self.device = get_device(self.device)
            self._processor = CLIPProcessor.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model = CLIPModel.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model.to(self.device).eval(); return True
        except Exception as exc:
            self._load_error = f"CLIP region probe unavailable: {type(exc).__name__}: {str(exc)[:180]}"; return False

    def classify(self, crop, attribute_type: str, labels: list[str], object_name: str = "") -> AttributeProbeResult:
        if not self._load(): return AttributeProbeResult({}, False, self._load_error or "CLIP unavailable")
        if attribute_type not in LABELS:
            return AttributeProbeResult({}, False, f"No configured region probe for attribute type '{attribute_type}'.")
        try:
            import torch
            inputs = self._processor(text=prompts_for(attribute_type, labels, object_name), images=crop,
                                     return_tensors="pt", padding=True).to(self.device)
            with torch.no_grad(): logits = self._model(**inputs).logits_per_image[0]
            values = torch.softmax(logits, dim=0).tolist()
            return AttributeProbeResult({label: round(float(value), 5) for label, value in zip(labels, values)}, backend=f"clip:{self.model_id}")
        except Exception as exc:
            return AttributeProbeResult({}, False, f"CLIP region inference failed: {type(exc).__name__}: {str(exc)[:180]}")


def crop_data_url(image_path: str, box: list[float]) -> str | None:
    """Small audit/display crop. It is returned only for actual grounded boxes."""
    try:
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        x1, y1, x2, y2 = [int(round(v)) for v in box]
        crop = image.crop((max(0, x1), max(0, y1), min(image.width, x2), min(image.height, y2)))
        if crop.width < 2 or crop.height < 2: return None
        crop.thumbnail((256, 256))
        stream = io.BytesIO(); crop.save(stream, format="JPEG", quality=85)
        return "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode("ascii")
    except Exception:
        return None


class AttributeVerifier:
    def __init__(self, probe: AttributeProbe | None = None, threshold: float = .50, cache: VerificationCache | None = None):
        self.probe, self.threshold, self.cache = probe or CLIPRegionProbe(), threshold, cache

    def _probabilities(self, image, image_path, box, attribute_type, object_name) -> AttributeProbeResult:
        key = f"{image_sha256(image_path)}|{object_name}|{','.join(f'{v:.1f}' for v in box)}|{attribute_type}" if self.cache else ""
        if self.cache:
            row = self.cache.get(key)
            if row is not None:
                add_cost(row.get("ms", 0.0))
                return AttributeProbeResult(row["probs"], backend=row.get("backend", "clip") + ":cached")
        x1, y1, x2, y2 = [int(round(v)) for v in box]
        crop = image.crop((max(0, x1), max(0, y1), min(image.width, x2), min(image.height, y2)))
        warm = getattr(self.probe, "_model", True) is not None
        started = perf_counter()
        result = self.probe.classify(crop, attribute_type, LABELS[attribute_type], object_name)
        if not warm and getattr(self.probe, "_model", None) is not None:  # first call loaded CLIP: time a warm call
            started = perf_counter()
            self.probe.classify(crop, attribute_type, LABELS[attribute_type], object_name)
        ms = (perf_counter() - started) * 1000
        add_cost(ms)
        if self.cache and result.available:
            self.cache.put(key, {"probs": result.probabilities, "backend": result.backend, "ms": round(ms, 1)})
        return result

    def verify(self, image_path: str, boxes: list[list[float]], box_scores: list[float], attribute_type: str,
               attribute_value: str, claim_id: str = "", object_name: str = ""):
        from core.schemas import Evidence
        from PIL import Image
        if not boxes:
            return Evidence(claim_id, "UNSUPPORTED", 0.0, ["grounding-dino"], explanation="No localized object region is available for attribute verification.", evidence_quality=1.0, diagnosis="UNSUPPORTED_CLAIM", binding_status="AMBIGUOUS")
        if attribute_type not in LABELS:
            return Evidence(claim_id, "AMBIGUOUS", .5, ["region-attribute-probe"], explanation=f"No region-level probe is configured for {attribute_type}.", evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM", binding_status="AMBIGUOUS")
        image = Image.open(image_path).convert("RGB")
        ranked = sorted(zip(boxes, box_scores or [0.0] * len(boxes)), key=lambda row: -row[1])[:MAX_BOXES]
        rows = []
        for box, detection in ranked:
            probe = self._probabilities(image, image_path, box, attribute_type, object_name)
            if not probe.available:
                return Evidence(claim_id, "AMBIGUOUS", .5, [probe.backend], explanation=probe.reason, evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM", binding_status="AMBIGUOUS", boxes=boxes)
            rows.append((detection * probe.probabilities.get(attribute_value, 0.0), detection, box, probe.probabilities))
        # Eq. 2: the binding holds only on the same region as the object.
        score, detection, box, probabilities = max(rows, key=lambda row: row[0])
        claimed = probabilities.get(attribute_value, 0.0)
        # A contradiction needs strong alternative evidence on the most confident instance.
        _, primary_detection, primary_box, primary = max(rows, key=lambda row: row[1])
        observed = max(primary, key=primary.get)
        if claimed >= self.threshold:
            status, diagnosis, binding, shown = "SUPPORTED", None, "CORRECT", box
            explanation = f"Same-region score for {attribute_value} is {score:.3f} (detection {detection:.3f} × crop probability {claimed:.3f})."
        elif observed != attribute_value and primary[observed] >= self.threshold:
            status, diagnosis, binding, shown = "CONTRADICTED", "ATTRIBUTE_BINDING_ERROR", "INCORRECT", primary_box
            explanation = f"Localized region supports {observed} ({primary[observed]:.3f}), not claimed {attribute_value} ({primary.get(attribute_value, 0):.3f})."
        else:
            status, diagnosis, binding, shown = "UNSUPPORTED", "UNSUPPORTED_CLAIM", "AMBIGUOUS", box
            explanation = f"Same-region evidence is insufficient for {attribute_value}; score {score:.3f}."
        crop_url = crop_data_url(image_path, shown)
        return Evidence(claim_id, status, round(score, 3), ["grounding-dino", "clip-region-probe"], confidence=round(score, 3), boxes=[shown],
                        verified_value=observed if status == "CONTRADICTED" else None, explanation=explanation, evidence_quality=1.0,
                        diagnosis=diagnosis, binding_status=binding, region_crop=crop_url,
                        signals={"open_vocabulary_grounding": {"available": True, "score": detection, "box": box},
                                 "region_attribute_probe": {"available": True, "attribute_type": attribute_type,
                                                            "claimed_probability": claimed, "probabilities": probabilities,
                                                            "primary_instance_probabilities": primary,
                                                            "equation": "s_attr(o,a)=max_{b in B_o} d_b*P(a|crop_b)", "crop": crop_url}})
