"""Verifier plumbing: cache, cache-only mode, transformers API drift, counting."""
import pytest
from PIL import Image

from verification.cache import CacheMiss, VerificationCache
from verification.grounding import CachedGrounder, GroundingDINO, GroundingResult, _post_process
from verification.service import count_instances


class CountingGrounder:
    def __init__(self): self.calls = 0
    def detect(self, image_path, object_name):
        self.calls += 1
        return GroundingResult(object_name, [[0, 0, 5, 5]], [.7])


def test_cache_reuses_detections_across_instances(tmp_path):
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)
    path = tmp_path / "cache.jsonl"
    grounder = CountingGrounder()
    first = CachedGrounder(grounder, VerificationCache(path)).detect(str(image), "dog")
    second = CachedGrounder(grounder, VerificationCache(path)).detect(str(image), "Dog")
    assert grounder.calls == 1 and first.scores == second.scores == [.7]


def test_cache_only_raises_instead_of_loading_models(tmp_path):
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)
    with pytest.raises(CacheMiss):
        CachedGrounder(CountingGrounder(), VerificationCache(tmp_path / "c.jsonl", cache_only=True)).detect(str(image), "cat")


def test_full_resolution_runs_never_read_cpu_resized_cache_entries(tmp_path):
    assert GroundingDINO(device="cpu", cpu_image_size=(480, 800)).cache_tag() == "480x800"
    assert GroundingDINO(device="cuda", cpu_image_size=(480, 800)).cache_tag() == ""
    assert GroundingDINO(device="cpu").cache_tag() == ""
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)
    cache = VerificationCache(tmp_path / "cache.jsonl")
    full, resized = CountingGrounder(), CountingGrounder()
    resized.cache_tag = lambda: "480x800"
    CachedGrounder(resized, cache).detect(str(image), "dog")
    CachedGrounder(full, cache).detect(str(image), "dog")
    assert full.calls == resized.calls == 1


def test_cpu_cache_only_reprocessing_reuses_full_resolution_gpu_results(tmp_path):
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)
    path = tmp_path / "cache.jsonl"
    CachedGrounder(CountingGrounder(), VerificationCache(path)).detect(str(image), "dog")  # e.g. Kaggle GPU run
    laptop = CountingGrounder(); laptop.cache_tag = lambda: "480x800"
    result = CachedGrounder(laptop, VerificationCache(path, cache_only=True)).detect(str(image), "dog")
    assert laptop.calls == 0 and result.scores == [.7]
    with pytest.raises(CacheMiss):
        CachedGrounder(laptop, VerificationCache(path, cache_only=True)).detect(str(image), "cat")


def test_outage_is_never_cached(tmp_path):
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)

    class Down:
        def detect(self, image_path, object_name): return GroundingResult(object_name, available=False, reason="offline")
    cache = VerificationCache(tmp_path / "c.jsonl")
    CachedGrounder(Down(), cache).detect(str(image), "cat")
    assert not (tmp_path / "c.jsonl").exists()


class NewAPI:
    def post_process_grounded_object_detection(self, outputs, input_ids, threshold, text_threshold, target_sizes):
        return [{"api": "threshold", "t": threshold}]


class OldAPI:
    def post_process_grounded_object_detection(self, outputs, input_ids, box_threshold, text_threshold, target_sizes):
        return [{"api": "box_threshold", "t": box_threshold}]


def test_grounding_post_process_supports_both_transformers_apis():
    assert _post_process(NewAPI(), None, None, .1, None)["api"] == "threshold"
    assert _post_process(OldAPI(), None, None, .1, None)["api"] == "box_threshold"


def test_count_uses_nms_and_support_threshold():
    boxes = [[0, 0, 10, 10], [1, 1, 10, 10], [0, 0, 9, 9], [50, 50, 60, 60], [80, 80, 90, 90]]
    scores = [.9, .8, .7, .6, .1]
    assert len(count_instances(boxes, scores, threshold=.3)) == 2
