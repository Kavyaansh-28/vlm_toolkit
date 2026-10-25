"""Open-vocabulary grounding backends used for existence verification.

This module intentionally has no closed-set detector fallback.  The default
backend is Grounding DINO from Transformers; when its weights cannot be loaded
(for example on an offline machine) callers receive an explicit unavailable
result rather than a fabricated detection score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class GroundingResult:
    object_name: str
    boxes: list[list[float]] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    available: bool = True
    reason: str = ""
    backend: str = "grounding-dino"


class Grounder(Protocol):
    def detect(self, image_path: str, object_name: str) -> GroundingResult: ...


class GroundingDINO:
    """Lazy Hugging Face Grounding DINO adapter.

    ``local_files_only`` defaults to false so a configured online workstation
    can fetch official model weights once.  It is configurable to make
    reproducible/offline evaluation fail explicitly instead of contacting a
    registry unexpectedly.
    """
    def __init__(self, model_id: str = "IDEA-Research/grounding-dino-tiny", threshold: float = .30,
                 local_files_only: bool = False):
        self.model_id, self.threshold, self.local_files_only = model_id, threshold, local_files_only
        self._processor = self._model = None
        self._load_error: str | None = None

    def _load(self) -> bool:
        if self._processor is not None:
            return True
        if self._load_error:
            return False
        try:
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
            self._processor = AutoProcessor.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            self._model.eval()
            return True
        except Exception as exc:  # dependency/model access boundary
            self._load_error = f"Grounding DINO unavailable: {type(exc).__name__}: {str(exc)[:180]}"
            return False

    def detect(self, image_path: str, object_name: str) -> GroundingResult:
        if not self._load():
            return GroundingResult(object_name, available=False, reason=self._load_error or "Grounding DINO unavailable")
        try:
            from PIL import Image
            image = Image.open(image_path).convert("RGB")
            # Grounding DINO uses dot-separated noun phrases as its text prompt.
            prompt = object_name.strip().lower().rstrip(".") + "."
            inputs = self._processor(images=image, text=prompt, return_tensors="pt")
            outputs = self._model(**inputs)
            target_sizes = [image.size[::-1]]
            result = self._processor.post_process_grounded_object_detection(
                outputs, inputs.input_ids, box_threshold=self.threshold, text_threshold=self.threshold,
                target_sizes=target_sizes,
            )[0]
            boxes = [[round(float(x), 2) for x in box.tolist()] for box in result.get("boxes", [])]
            scores = [round(float(x), 5) for x in result.get("scores", [])]
            return GroundingResult(object_name, boxes, scores, backend=f"grounding-dino:{self.model_id}")
        except Exception as exc:
            return GroundingResult(object_name, available=False,
                                   reason=f"Grounding DINO inference failed: {type(exc).__name__}: {str(exc)[:180]}")

