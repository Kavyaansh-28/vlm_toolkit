"""Small JSON API for the React client."""
from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agent import RajasthanAgent
from tools import get_transport_options

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DEFAULT_ORIGINS = {"http://localhost:8443", "http://127.0.0.1:8443", "http://localhost:5173", "http://127.0.0.1:5173"}


class ApiHandler(BaseHTTPRequestHandler):
    """Adapt the bounded planner to a browser-friendly JSON endpoint."""

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        configured = {x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()}
        allowed = configured or DEFAULT_ORIGINS
        if origin in allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        origin = self.headers.get("Origin")
        configured = {x.strip() for x in os.getenv("CORS_ORIGINS", "").split(",") if x.strip()}
        allowed = configured or DEFAULT_ORIGINS
        if origin in allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path.rstrip("/") == "/api/health":
            self._send_json({"status": "ok", "llm_enabled": bool(os.getenv("OPENAI_API_KEY")), "places_enabled": bool(os.getenv("GOOGLE_PLACES_API_KEY")), "transport_live": False})
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        path = self.path.rstrip("/")
        if path not in {"/api/chat", "/api/transport/options"}:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 65536:
                self._send_json({"error": "Request body must be between 1 byte and 64 KiB."}, HTTPStatus.BAD_REQUEST)
                return
            payload = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(payload, dict):
                self._send_json({"error": "Request body must be a JSON object."}, HTTPStatus.BAD_REQUEST)
                return
            if path == "/api/transport/options":
                origin, destination = payload.get("origin"), payload.get("destination")
                if not isinstance(origin, str) or not isinstance(destination, str) or not origin.strip() or not destination.strip():
                    self._send_json({"error": "Origin and destination are required."}, HTTPStatus.BAD_REQUEST)
                    return
                if len(origin) > 100 or len(destination) > 100:
                    self._send_json({"error": "City names must be at most 100 characters."}, HTTPStatus.BAD_REQUEST)
                    return
                self._send_json(get_transport_options(origin, destination))
                return
            message = payload.get("message", "")
            if not isinstance(message, str) or len(message) > 4000:
                self._send_json({"error": "Message must be text of at most 4,000 characters."}, HTTPStatus.BAD_REQUEST)
                return
            message = message.strip()
            context = payload.get("context") or {}
            if not message:
                self._send_json({"error": "A message is required."}, HTTPStatus.BAD_REQUEST)
                return
            if not isinstance(context, dict):
                self._send_json({"error": "Context must be an object."}, HTTPStatus.BAD_REQUEST)
                return
            self._send_json(RajasthanAgent().run(message, context))
        except (ValueError, TypeError, json.JSONDecodeError):
            self._send_json({"error": "Request body must be valid JSON."}, HTTPStatus.BAD_REQUEST)
        except Exception:
            self._send_json({"error": "The planner could not complete that request. Please try again."}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format, *args):
        if os.getenv("API_REQUEST_LOGS"):
            super().log_message(format, *args)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"Rajasthan Explorer API listening on http://127.0.0.1:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), ApiHandler).serve_forever()
