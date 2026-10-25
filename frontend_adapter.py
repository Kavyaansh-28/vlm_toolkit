"""Small HTTP compatibility adapter for the standalone Next.js frontend.

It deliberately delegates to the existing Python pipeline/database modules;
this file adds transport only and does not alter backend logic or schemas.
Run with: python frontend_adapter.py
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import socket
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import yaml

from claims.graph import graph_data
from core.pipeline import run
from database.db import recent, save
from evaluation.metrics import classification_metrics
from vlm import providers

ROOT = Path(__file__).resolve().parent
MAX_IMAGE_BYTES = 15 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    server_version = "VLMFrontendAdapter/1.0"
    # HTTP/1.1 is required for proper connection handling with the Next.js proxy.
    protocol_version = "HTTP/1.1"

    def handle(self) -> None:
        """Wrap the entire request lifecycle so an unexpected error never
        silently resets the TCP connection (which the proxy reports as
        'socket hang up' / ECONNRESET)."""
        try:
            super().handle()
        except Exception:
            traceback.print_exc()

    def log_message(self, fmt: str, *args) -> None:
        print(f"[frontend-api] {self.address_string()} {fmt % args}", flush=True)

    def _send(self, status: int, payload: object) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(encoded)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            # The browser/proxy may cancel a slow analysis; it is too late to send
            # a second response, so let the worker exit without a traceback.
            return

    def _read_body(self) -> bytes:
        """Read the full request body, handling both Content-Length and
        chunked Transfer-Encoding (which Next.js's proxy may use)."""
        transfer_encoding = (self.headers.get("Transfer-Encoding") or "").lower()
        if "chunked" in transfer_encoding:
            parts: list[bytes] = []
            total = 0
            while True:
                line = self.rfile.readline()
                if not line:
                    break
                chunk_size = int(line.strip(), 16)
                if chunk_size == 0:
                    self.rfile.readline()  # consume trailing CRLF
                    break
                chunk = self.rfile.read(chunk_size)
                self.rfile.readline()  # consume trailing CRLF
                total += len(chunk)
                if total > MAX_IMAGE_BYTES * 2:
                    raise ValueError("Request exceeds the upload limit")
                parts.append(chunk)
            return b"".join(parts)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid content length") from exc
        if length <= 0 or length > MAX_IMAGE_BYTES * 2:
            raise ValueError("Request is empty or exceeds the upload limit")
        return self.rfile.read(length)

    def _read_json(self) -> dict:
        raw = self._read_body()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Request body must be valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError("Request body must be an object")
        return data

    def do_OPTIONS(self) -> None:
        self._send(204, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/health":
            self._send(200, {"status": "ok"})
            return
        if path == "/api/config":
            config = yaml.safe_load((ROOT / "config/config.yaml").read_text())
            options = providers()
            default = config.get("vlm", {}).get("provider")
            reliability = config.get("reliability", {})
            vlm = config.get("vlm", {})
            self._send(200, {
                "providers": options,
                "provider": default if default in options else (options[0] if options else ""),
                "defaults": {
                    "candidate_count": vlm.get("candidate_count", 3),
                    "verification_weight": reliability.get("lambda_verification", 0.75),
                    "agreement_weight": reliability.get("lambda_agreement", 0.25),
                    "high_threshold": reliability.get("high_threshold", 0.8),
                    "low_threshold": reliability.get("low_threshold", 0.4),
                },
            })
            return
        if path == "/api/evaluation":
            self._send(200, classification_metrics([]))
            return
        if path == "/api/history":
            rows = recent(100)
            self._send(200, [{"id": row[0], "created_at": row[1], "query": row[2]} for row in rows])
            return
        if path.startswith("/api/history/"):
            try:
                item_id = int(path.rsplit("/", 1)[-1])
            except ValueError:
                self._send(400, {"error": "Invalid experiment id"})
                return
            row = next((row for row in recent(1000) if row[0] == item_id), None)
            if not row:
                self._send(404, {"error": "Experiment not found"})
                return
            self._send(200, {"id": row[0], "created_at": row[1], "query": row[2], "payload": json.loads(row[3])})
            return
        self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path.rstrip("/") != "/api/analyze":
            self._send(404, {"error": "Not found"})
            return
        image_path: str | None = None
        try:
            body = self._read_json()
            encoded = body.get("image_base64", "")
            if not isinstance(encoded, str) or not encoded:
                raise ValueError("An image is required")
            try:
                image_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("Image data is not valid base64") from exc
            if not image_bytes or len(image_bytes) > MAX_IMAGE_BYTES:
                raise ValueError("Image is empty or exceeds the 15 MB limit")
            name = Path(str(body.get("filename", "upload.png"))).name
            suffix = Path(name).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                suffix = ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
                temp.write(image_bytes)
                image_path = temp.name

            query = str(body.get("query", "Describe the objects and their colors."))[:2000]
            count = max(1, min(3, int(body.get("candidate_count", 3))))
            weights = body.get("weights", {})
            if not isinstance(weights, dict):
                weights = {}
            reliability_config = yaml.safe_load((ROOT / "config/config.yaml").read_text()).get("reliability", {})
            weight_values = {
                "verification": _number(weights.get("verification", 0.6), 0, 1),
                "probability": _number(weights.get("probability", reliability_config.get("lambda_probability", 0.0)), 0, 1),
                "agreement": _number(weights.get("agreement", 0.2), 0, 1),
            }
            high = _number(body.get("high_threshold", 0.8), 0.5, 1)
            low = _number(body.get("low_threshold", 0.4), 0, 0.5)
            provider = str(body.get("provider", ""))
            verifier_provider = str(body.get("verifier_provider") or provider)
            if provider not in providers() or verifier_provider not in providers():
                raise ValueError("Select configured generator and verifier VLM providers")
            manual = str(body.get("manual_response", ""))[:12000]
            candidates, error = run(image_path, query, count, weight_values, manual, high, low, provider, verifier_provider)
            if not candidates:
                self._send(502, {"error": error or "Verification engine unavailable"})
                return
            stored_candidates = [candidate.export() for candidate in candidates]
            response_candidates = []
            for candidate, exported in zip(candidates, stored_candidates):
                response_candidates.append({**exported, "graph": graph_data(candidate.claims)})
            image_id = hashlib.sha256(image_bytes).hexdigest()
            configuration = {"generator_provider": provider, "verifier_provider": verifier_provider,
                             "candidate_count": count, "weights": weight_values,
                             "high_threshold": high, "low_threshold": low}
            stored_payload = {"query": query, "image_id": image_id, "configuration": configuration,
                              "candidates": stored_candidates}
            experiment_id = save(query, stored_payload)
            self._send(200, {"experiment_id": experiment_id,
                             "analysis": {"query": query, "image_id": image_id,
                                          "experiment_id": experiment_id, "candidates": response_candidates},
                             "warning": error})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # transport boundary: keep the running server alive
            self._send(502, {"error": f"Verification request failed: {type(exc).__name__}: {str(exc)[:300]}"})
        finally:
            if image_path:
                Path(image_path).unlink(missing_ok=True)


def _number(value: object, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Thresholds and weights must be numeric") from exc
    if not minimum <= number <= maximum:
        raise ValueError("Threshold or weight is outside its allowed range")
    return number


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    port = int(os.environ.get("VLM_API_PORT", "8010"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    print(f"VLM frontend adapter listening at http://127.0.0.1:{port}", flush=True)
    server.serve_forever()
