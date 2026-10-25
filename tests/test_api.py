"""FastAPI routes with the manual-candidate path and a fake verifier (no models, no API keys)."""
import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import database.db as db
from api import server
from evaluation.fake import fake_verify


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB", tmp_path / "experiments.db")
    monkeypatch.setattr("verification.service.verify", fake_verify)
    return TestClient(server.app)


def _image() -> str:
    stream = io.BytesIO(); Image.new("RGB", (16, 16), "red").save(stream, format="PNG")
    return base64.b64encode(stream.getvalue()).decode()


def test_health_and_config(client):
    assert client.get("/health").json() == {"status": "ok"}
    config = client.get("/api/config").json()
    assert "hf-local" in config["providers"] and "thresholds" in config["defaults"]


def test_analyze_review_history_round_trip(client):
    body = {"image_base64": _image(), "filename": "x.png", "provider": "gemini", "candidate_count": 2,
            "manual_response": "A dog with a giraffe sits on a bench. ||| A dog on a bench."}
    response = client.post("/api/analyze", json=body)
    assert response.status_code == 200, response.text
    analysis = response.json()["analysis"]
    first = analysis["candidates"][0]
    assert first["selected"] and "claim_actions" in first and "graph" in first
    history = client.get("/api/history").json()
    assert history and client.get(f"/api/history/{history[0]['id']}").json()["payload"]["selected_candidate"] == first["id"]
    queue = client.get("/api/review").json()
    assert isinstance(queue, list)
    if queue:
        item = queue[0]
        saved = client.post("/api/review", json={"experiment_id": item["experiment_id"], "claim_id": item["claim_id"], "label": "correct"})
        assert saved.json() == {"status": "saved"}
        assert client.get("/api/review").json()[0]["label"] == "correct"


def test_rejects_bad_input(client):
    assert client.post("/api/analyze", json={"image_base64": "!!", "provider": "gemini"}).status_code == 400
    assert client.post("/api/analyze", json={"image_base64": _image(), "provider": "nope"}).status_code == 400
    assert client.post("/api/review", json={"experiment_id": 999, "claim_id": "x", "label": "correct"}).status_code == 404


def test_benchmarks_not_run(client, monkeypatch, tmp_path):
    monkeypatch.setattr(server, "REPORT", tmp_path / "missing.json")
    assert client.get("/api/benchmarks").json()["status"] == "NOT RUN"
