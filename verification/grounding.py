"""Open-vocabulary grounding backends used for existence verification.

This module intentionally has no closed-set detector fallback.  The default
backend is Grounding DINO from Transformers; when its weights cannot be loaded
(for example on an offline machine) callers receive an explicit unavailable
result rather than a fabricated detection score.
"""
from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass, field
from time import perf_counter
from typing import Protocol

from verification.cache import VerificationCache, add_cost, image_sha256


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


def _post_process(processor, outputs, input_ids, threshold: float, target_sizes):
    # transformers renamed ``box_threshold`` to ``threshold``; pick the keyword from the
    # signature rather than catching TypeError, which could mask unrelated errors.
    post_process = processor.post_process_grounded_object_detection
    parameters = inspect.signature(post_process).parameters
    if "threshold" in parameters:
        score_threshold = {"threshold": threshold}
    elif "box_threshold" in parameters:
        score_threshold = {"box_threshold": threshold}
    else:
        raise TypeError("Grounding DINO post-processor has no supported box-threshold parameter")
    return post_process(outputs, input_ids, **score_threshold, text_threshold=threshold, target_sizes=target_sizes)[0]


class GroundingDINO:
    """Lazy Hugging Face Grounding DINO adapter.

    ``threshold`` is the detection floor: boxes at or above it are returned so
    s_obj stays a real score below the support threshold.  ``local_files_only``
    makes reproducible/offline evaluation fail explicitly instead of contacting
    a registry unexpectedly.  ``cpu_image_size`` (shortest, longest edge) shrinks the
    model input when running on CPU, where full resolution costs ~17 s per object.
    """
    def __init__(self, model_id: str = "IDEA-Research/grounding-dino-tiny", threshold: float = .10,
                 local_files_only: bool = False, device: str = "auto", cpu_image_size: tuple[int, int] | None = None):
        self.model_id, self.threshold, self.local_files_only = model_id, threshold, local_files_only
        self.device, self.cpu_image_size = device, cpu_image_size
        self._processor = self._model = None
        self._load_error: str | None = None
        self._lock = threading.Lock()  # API requests run in a thread pool; load the model once

    def _load(self) -> bool:
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:  # another thread finished loading while we waited
                return True
            if self._load_error:
                return False
            return self._load_locked()

    def _load_locked(self) -> bool:
        try:
            from transformers import AutoModelForZeroShotObjectDetection, AutoProcessor
            from utils import get_device
            self.device = get_device(self.device)
            processor = AutoProcessor.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            model = AutoModelForZeroShotObjectDetection.from_pretrained(self.model_id, local_files_only=self.local_files_only)
            model.to(self.device).eval()
            if self.cache_tag():
                shortest, longest = self.cpu_image_size
                processor.image_processor.size = {"shortest_edge": shortest, "longest_edge": longest}
            self._processor, self._model = processor, model  # publish only when fully ready
            return True
        except Exception as exc:  # dependency/model access boundary
            self._load_error = f"Grounding DINO unavailable: {type(exc).__name__}: {str(exc)[:180]}"
            return False

    def cache_tag(self) -> str:
        """Non-empty when inputs are resized, so those scores never share cache entries with full-resolution ones."""
        from utils import get_device
        if self.cpu_image_size and get_device(self.device) == "cpu":
            return "{}x{}".format(*self.cpu_image_size)
        return ""

    def detect(self, image_path: str, object_name: str) -> GroundingResult:
        if not self._load():
            return GroundingResult(object_name, available=False, reason=self._load_error or "Grounding DINO unavailable")
        try:
            import torch
            from PIL import Image
            image = Image.open(image_path).convert("RGB")
            # Grounding DINO uses dot-separated noun phrases as its text prompt.
            prompt = object_name.strip().lower().rstrip(".") + "."
            inputs = self._processor(images=image, text=prompt, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                outputs = self._model(**inputs)
            result = _post_process(self._processor, outputs, inputs.input_ids, self.threshold, [image.size[::-1]])
            boxes = [[round(float(x), 2) for x in box.tolist()] for box in result.get("boxes", [])]
            scores = [round(float(x), 5) for x in result.get("scores", [])]
            return GroundingResult(object_name, boxes, scores, backend=f"grounding-dino:{self.model_id}")
        except Exception as exc:
            return GroundingResult(object_name, available=False,
                                   reason=f"Grounding DINO inference failed: {type(exc).__name__}: {str(exc)[:180]}")


class CachedGrounder:
    """Wrap any grounder with the on-disk verification cache."""
    def __init__(self, grounder: Grounder, cache: VerificationCache):
        self.grounder, self.cache = grounder, cache

    def detect(self, image_path: str, object_name: str) -> GroundingResult:
        base = f"{image_sha256(image_path)}|{object_name.strip().lower()}"
        tag = getattr(self.grounder, "cache_tag", lambda: "")()
        # A resized (CPU) run may reuse full-resolution results, e.g. GPU caches from Kaggle reprocessed
        # with --cache-only on a laptop; a full-resolution run never reads resized ones.
        key, fallbacks = (f"{base}|{tag}", (base,)) if tag else (base, ())
        row = self.cache.get(key, *fallbacks)
        if row is not None:
            add_cost(row.get("ms", 0.0))
            return GroundingResult(object_name, row["boxes"], row["scores"], backend=row.get("backend", "grounding-dino") + ":cached")
        warm = getattr(self.grounder, "_model", True) is not None  # exclude first-call model loading
        started = perf_counter()
        result = self.grounder.detect(image_path, object_name)
        ms = (perf_counter() - started) * 1000
        if not warm and getattr(self.grounder, "_model", None) is not None:
            ms = self._timed_rerun(image_path, object_name, ms)
        add_cost(ms)
        if result.available:  # never cache an outage as "no detection"
            self.cache.put(key, {"boxes": result.boxes, "scores": result.scores, "backend": result.backend, "ms": round(ms, 1)})
        return result

    def _timed_rerun(self, image_path: str, object_name: str, fallback: float) -> float:
        """The first call also loaded the model; time a second, warm inference instead."""
        started = perf_counter()
        rerun = self.grounder.detect(image_path, object_name)
        return (perf_counter() - started) * 1000 if rerun.available else fallback
