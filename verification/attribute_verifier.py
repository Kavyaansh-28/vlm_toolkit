"""Region-level attribute checks for attribute-binding claims.

The probe only receives a crop from a grounded object box.  It therefore
cannot validate ``blue car`` merely because blue occurs elsewhere in the image.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Protocol

from claims import COLORS


@dataclass
class AttributeProbeResult:
    probabilities: dict[str, float]
    available: bool = True
    reason: str = ""
    backend: str = "clip-region-probe"


class AttributeProbe(Protocol):
    def classify(self, crop, attribute_type: str, labels: list[str]) -> AttributeProbeResult: ...


class CLIPRegionProbe:
    def __init__(self, model_id: str = "openai/clip-vit-base-patch32", local_files_only: bool = False):
        self.model_id, self.local_files_only = model_id, local_files_only
        self._processor = self._model = None
        self._load_error: str | None = None

    def _load(self) -> bool:
        if self._processor is not None: return True
        if self._load_error: return False
        try:
            from transformers import CLIPModel, CLIPProcessor
            self._processor = CLIPProcessor.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model = CLIPModel.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model.eval(); return True
        except Exception as exc:
            self._load_error = f"CLIP region probe unavailable: {type(exc).__name__}: {str(exc)[:180]}"; return False

    def classify(self, crop, attribute_type: str, labels: list[str]) -> AttributeProbeResult:
        if not self._load(): return AttributeProbeResult({}, False, self._load_error or "CLIP unavailable")
        if attribute_type != "color":
            return AttributeProbeResult({}, False, f"No configured region probe for attribute type '{attribute_type}'.")
        try:
            import torch
            prompts = [f"a {label} object" for label in labels]
            inputs = self._processor(text=prompts, images=crop, return_tensors="pt", padding=True)
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
    def __init__(self, probe: AttributeProbe | None = None, threshold: float = .50):
        self.probe, self.threshold = probe or CLIPRegionProbe(), threshold

    def verify(self, image_path: str, boxes: list[list[float]], box_scores: list[float], attribute_type: str,
               attribute_value: str, claim_id: str = ""):
        from core.schemas import Evidence
        from PIL import Image
        if not boxes:
            return Evidence(claim_id, "UNSUPPORTED", 0.0, ["grounding-dino"], explanation="No localized object region is available for attribute verification.", evidence_quality=1.0, diagnosis="UNSUPPORTED_CLAIM", binding_status="AMBIGUOUS")
        if attribute_type != "color":
            return Evidence(claim_id, "AMBIGUOUS", .5, ["region-attribute-probe"], explanation=f"No region-level probe is configured for {attribute_type}.", evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM", binding_status="AMBIGUOUS")
        image = Image.open(image_path).convert("RGB")
        candidates = []
        for index, box in enumerate(boxes):
            x1, y1, x2, y2 = [int(round(v)) for v in box]
            crop = image.crop((max(0,x1), max(0,y1), min(image.width,x2), min(image.height,y2)))
            probe = self.probe.classify(crop, attribute_type, list(COLORS[:-1]))
            if not probe.available:
                return Evidence(claim_id, "AMBIGUOUS", .5, [probe.backend], explanation=probe.reason, evidence_quality=0.0, diagnosis="AMBIGUOUS_CLAIM", binding_status="AMBIGUOUS", boxes=boxes)
            p_claimed = probe.probabilities.get(attribute_value, 0.0)
            detection = box_scores[index] if index < len(box_scores) else 0.0
            candidates.append((detection * p_claimed, detection, box, probe.probabilities, crop_data_url(image_path, box)))
        best = max(candidates, key=lambda row: row[0])
        score, detection, box, probabilities, crop_url = best
        observed = max(probabilities, key=probabilities.get)
        # Binding contradiction requires strong *alternative* evidence on the same crop.
        alternative = probabilities[observed]
        if score >= self.threshold:
            status, diagnosis, binding = "SUPPORTED", None, "CORRECT"
            explanation = f"Same-region score for {attribute_value} is {score:.3f} (detection {detection:.3f} × crop probability {probabilities.get(attribute_value, 0):.3f})."
        elif observed != attribute_value and alternative >= self.threshold:
            status, diagnosis, binding = "CONTRADICTED", "ATTRIBUTE_BINDING_ERROR", "INCORRECT"
            explanation = f"Localized region supports {observed} ({alternative:.3f}), not claimed {attribute_value} ({probabilities.get(attribute_value, 0):.3f})."
        else:
            status, diagnosis, binding = "UNSUPPORTED", "UNSUPPORTED_CLAIM", "AMBIGUOUS"
            explanation = f"Same-region evidence is insufficient for {attribute_value}; score {score:.3f}."
        return Evidence(claim_id, status, round(score, 3), ["grounding-dino", "clip-region-probe"], confidence=round(score, 3), boxes=[box], verified_value=observed if status == "CONTRADICTED" else None, explanation=explanation, evidence_quality=1.0, diagnosis=diagnosis, binding_status=binding, region_crop=crop_url,
                        signals={"open_vocabulary_grounding": {"available": True, "score": detection, "box": box}, "region_attribute_probe": {"available": True, "claimed_probability": probabilities.get(attribute_value, 0.0), "probabilities": probabilities, "equation": "s_attr(o,a)=max_{b in B_o} d_b*P(a|crop_b)", "crop": crop_url}})
