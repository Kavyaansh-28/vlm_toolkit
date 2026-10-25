"""API generator plumbing: upload size and candidate order (no network)."""
import io
import threading
import time

from PIL import Image

from vlm import API_IMAGE_MAX_SIDE, _image_payload
from vlm_engine import ProviderVLMEngine


def test_large_images_are_downscaled_to_jpeg_and_small_ones_sent_unchanged(tmp_path):
    large, small = tmp_path / "large.png", tmp_path / "small.png"
    Image.new("RGBA", (2752, 1536), (200, 30, 30, 255)).save(large)
    Image.new("RGB", (640, 480)).save(small)
    mime, data = _image_payload(str(large))
    assert mime == "image/jpeg" and max(Image.open(io.BytesIO(data)).size) == API_IMAGE_MAX_SIDE
    assert _image_payload(str(small)) == ("image/png", small.read_bytes())
    assert _image_payload(str(tmp_path / "notes.txt"))[0] is None


def test_api_candidates_run_concurrently_and_keep_greedy_first(monkeypatch):
    active, peak, lock = [0], [0], threading.Lock()

    def fake_generate(self, image_path, query, **kwargs):
        with lock:
            active[0] += 1; peak[0] = max(peak[0], active[0])
        time.sleep(.05)
        with lock:
            active[0] -= 1
        return {"response": f"t={kwargs['temperature']}"}

    monkeypatch.setattr(ProviderVLMEngine, "generate", fake_generate)
    rows = ProviderVLMEngine("gemini").generate_candidates("img.png", "q", 3, temperature=.7)
    assert [row["response"] for row in rows] == ["t=0.0", "t=0.7", "t=0.7"]
    assert peak[0] == 3 and all(row["generation_strategy"] == "repeated_api_calls" for row in rows)


def _provider_with(monkeypatch, outcomes):
    from vlm import GeminiProvider
    calls = []

    def fake_call(self, model, prompt, mime, data, temperature):
        calls.append(model)
        outcome = outcomes[model]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(GeminiProvider, "_call", fake_call)
    monkeypatch.delenv("GEMINI_FALLBACK_MODEL", raising=False)
    return GeminiProvider("gemini-3.8-flash", "key"), calls


def test_gemini_falls_back_when_the_primary_model_is_overloaded(monkeypatch, tmp_path):
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)
    provider, calls = _provider_with(monkeypatch, {"gemini-3.8-flash": RuntimeError("503 UNAVAILABLE. overloaded"),
                                                   "gemini-2.5-flash": "a red car"})
    row = provider.generate(str(image), "describe")
    assert calls == ["gemini-3.8-flash", "gemini-2.5-flash"] and row["response"] == "a red car"
    assert row["model"] == "gemini-2.5-flash" and "error" not in row


def test_gemini_does_not_retry_non_transient_errors(monkeypatch, tmp_path):
    image = tmp_path / "a.png"; Image.new("RGB", (8, 8)).save(image)
    provider, calls = _provider_with(monkeypatch, {"gemini-3.8-flash": RuntimeError("400 INVALID_ARGUMENT")})
    row = provider.generate(str(image), "describe")
    assert calls == ["gemini-3.8-flash"] and row["response"] == "" and "400 INVALID_ARGUMENT" in row["error"]
