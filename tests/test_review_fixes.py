"""Regression tests for the PR #1 review findings."""
import json
import threading
import time
from pathlib import Path

from core.config import PipelineConfig, load_config
from core.pipeline import process_candidates, run
from evaluation.evaluator import evaluate
from evaluation.fake import fake_verify
from evaluation.process import process_file
from evaluation.reports import markdown, write_report

ROOT = Path(__file__).resolve().parents[1]
CFG = PipelineConfig(lo=.3, hi=.7, rerank_threshold=.5, grounding_threshold=.3, candidate_count=3,
                     weights={"verification": .6, "probability": .2, "agreement": .2})


# Finding 1: the GitHub token must never land in saved notebook output.
def _notebook_sources():
    notebook = json.loads((ROOT / "kaggle" / "run_benchmarks.ipynb").read_text(encoding="utf-8"))
    yield "run_benchmarks.ipynb", "".join("".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code")
    yield "run_benchmarks.py", (ROOT / "kaggle" / "run_benchmarks.py").read_text(encoding="utf-8")


def test_kaggle_notebook_keeps_repository_and_token_out_of_saved_output():
    for name, source in _notebook_sources():
        assert "/kaggle/working/vlm" not in source, name           # repo (with .git/config) is not saved output
        assert 'WORKDIR = "/tmp/vlm"' in source, name
        assert '"remote", "set-url", "origin", f"https://{REPO_URL}"' in source, name
        clone_call = source.split('"git", "clone"')[1].split("\n    if clone.returncode")[0]
        assert "capture_output=True" in clone_call and "check=True" not in clone_call, name  # no command echo on failure
        assert "replace(token" in source, name                     # stderr is redacted before raising


def _write_gen(tmp_path: Path) -> Path:
    gen = tmp_path / "chair.jsonl"
    rows = [{"sample_id": f"c{i}", "benchmark": "chair", "split": "all", "image_path": "x.png", "gt_objects": ["dog"], "model": "m",
             "candidates": [{"text": "A dog with a giraffe.", "latency_ms": 100}, {"text": "A dog.", "latency_ms": 100}]} for i in range(3)]
    gen.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return gen


# Finding 2: every processed row records the settings used; the report reads them.
def test_rows_record_settings_and_report_uses_them(tmp_path):
    gen, proc = _write_gen(tmp_path), tmp_path / "proc"
    tuned = CFG.with_overrides(thresholds={"object": (.2, .6)}, tuned_from="results/tuned.yaml")
    process_file(gen, "full_toolkit", proc, tuned, fake_verify)
    row = json.loads((proc / "full_toolkit" / "chair.jsonl").read_text().splitlines()[0])
    assert row["config"]["thresholds"] == {"object": [.2, .6]} and row["config"]["tuned"] is True
    meta = evaluate(proc)["meta"]
    assert meta["consistent"] and meta["thresholds"] == {"object": [.2, .6]} and meta["tuned"] is True


def test_report_flags_mixed_and_untuned_settings(tmp_path):
    gen, proc = _write_gen(tmp_path), tmp_path / "proc"
    process_file(gen, "full_toolkit", proc, CFG, fake_verify)                                   # default thresholds
    process_file(gen, "n_equals_1", proc, CFG.with_overrides(tuned_from="tuned.yaml"), fake_verify)
    report = evaluate(proc)
    assert report["meta"]["consistent"] is False and report["meta"]["tuned"] is False
    assert "different settings" in markdown(write_report(report, tmp_path / "r.json", {}))


# Finding 4: the process stage resumes, but recomputes when settings change.
def test_process_resumes_from_partial_and_recomputes_on_new_settings(tmp_path):
    gen, proc = _write_gen(tmp_path), tmp_path / "proc"
    calls = {"n": 0}

    def counting_verify(image_path, claims, attribute=True):
        calls["n"] += 1
        return fake_verify(image_path, claims, attribute)

    out = proc / "full_toolkit" / "chair.jsonl"
    out.parent.mkdir(parents=True)
    # Simulate a crash after one row: only the partial file exists.
    process_file(gen, "full_toolkit", proc, CFG, counting_verify)
    first_row = out.read_text().splitlines()[0]
    out.unlink()
    out.with_name("chair.partial.jsonl").write_text(first_row + "\n")
    calls["n"] = 0
    process_file(gen, "full_toolkit", proc, CFG, counting_verify)
    assert calls["n"] == 2 * 2  # 2 remaining samples x 2 candidates; the finished one is reused
    assert len(out.read_text().splitlines()) == 3 and not out.with_name("chair.partial.jsonl").exists()
    calls["n"] = 0
    process_file(gen, "full_toolkit", proc, CFG.with_overrides(rerank_threshold=.9), counting_verify)
    assert calls["n"] == 3 * 2  # changed settings: nothing reused


# Finding 5: the live path passes the configured generation settings.
def test_live_run_passes_generation_settings(monkeypatch):
    seen = {}

    class Engine:
        def generate_candidates(self, image_path, query, n, **kwargs):
            seen.update(n=n, **kwargs)
            return [{"response": "A dog.", "model": "fake"}]

    monkeypatch.setattr("vlm_engine.get_engine", lambda provider: Engine())
    monkeypatch.setattr("verification.service.verify", fake_verify)
    run("x.png", "Describe.", "hf-local", CFG.with_overrides(candidate_count=2, temperature=.3, max_new_tokens=64, seed=7))
    assert seen == {"n": 2, "temperature": .3, "max_new_tokens": 64, "seed": 7}


def test_generation_settings_come_from_config():
    cfg = load_config(tuned="__none__")
    assert (cfg.temperature, cfg.max_new_tokens, cfg.seed) == (.7, 128, 42) and cfg.tuned_from is None


# Finding 6: a failed greedy candidate keeps its slot; only re-rank can replace it.
def test_failed_greedy_candidate_keeps_baseline_slot():
    rows = [{"response": "", "error": "CUDA OOM"}, {"response": "A dog on a bench."}, {"response": "A dog on a bench."}]
    out = process_candidates("x.png", rows, CFG, verify_fn=fake_verify)
    assert out[0].id != "candidate-1" and out[0].decision == "RERANK"
    failed = next(c for c in out if c.id == "candidate-1")
    assert failed.diagnosis == ["GENERATION_FAILED"] and "CUDA OOM" in failed.decision_reason


def test_failed_greedy_without_reliable_alternative_abstains():
    rows = [{"response": ""}, {"response": "A giraffe."}]
    out = process_candidates("x.png", rows, CFG, verify_fn=fake_verify)
    assert out[0].id == "candidate-1" and out[0].decision == "ABSTAIN" and "Generation failed" in out[0].decision_reason


def test_all_candidates_empty_returns_nothing():
    assert process_candidates("x.png", [{"response": ""}], CFG, verify_fn=fake_verify) == []


# Finding 7: concurrent first requests load each model exactly once.
def _slow_loader(model, counter):
    def load_locked():
        counter["n"] += 1
        time.sleep(.05)                     # widen the race window
        model._processor, model._model = object(), object()
        return True
    return load_locked


def _hammer(load, threads=8):
    workers = [threading.Thread(target=load) for _ in range(threads)]
    for worker in workers: worker.start()
    for worker in workers: worker.join()


def test_concurrent_first_use_loads_grounding_model_once():
    from verification.grounding import GroundingDINO
    model, loads = GroundingDINO(device="cpu"), {"n": 0}
    model._load_locked = _slow_loader(model, loads)
    _hammer(model._load)
    assert loads["n"] == 1


def test_concurrent_first_use_loads_clip_once():
    from verification.attribute_verifier import CLIPRegionProbe
    probe, loads = CLIPRegionProbe(device="cpu"), {"n": 0}
    probe._load_locked = _slow_loader(probe, loads)
    _hammer(probe._load)
    assert loads["n"] == 1
