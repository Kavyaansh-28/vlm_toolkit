#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
WEB_PORT="${VLM_WEB_PORT:-3000}"
API_PORT="${VLM_API_PORT:-8010}"
WEB_URL="http://127.0.0.1:${WEB_PORT}"
API_URL="http://127.0.0.1:${API_PORT}"
cd "$ROOT_DIR"

http_ok() {
  curl --silent --show-error --fail --max-time 2 "$1" >/dev/null 2>&1
}

frontend_is_ours() {
  local html
  html="$(curl --silent --fail --max-time 2 "$WEB_URL" 2>/dev/null || true)"
  [[ "$html" == *"VLM Reliability Layer"* || "$html" == *"VLM Reliability Lab"* || "$html" == *"checking AI"* ]]
}

if frontend_is_ours && http_ok "$API_URL/health"; then
  printf 'VLM Reliability Lab is already running.\nFrontend: %s\nAdapter:  %s\n' "$WEB_URL" "$API_URL"
  exit 0
fi

PYTHON_BIN="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="$ROOT_DIR/.venv/Scripts/python.exe"
if [[ ! -x "$PYTHON_BIN" ]]; then PYTHON_BIN=python3; fi
API_PID=""
if ! http_ok "$API_URL/health"; then
  "$PYTHON_BIN" -m uvicorn api.server:app --host 127.0.0.1 --port "$API_PORT" &
  API_PID=$!
  for _ in {1..30}; do
    if http_ok "$API_URL/health"; then break; fi
    sleep 0.25
  done
  if ! http_ok "$API_URL/health"; then
    echo "Could not start the frontend adapter on port ${API_PORT}. If it is already running, verify ${API_URL}/health." >&2
    exit 1
  fi
fi

cleanup() {
  if [[ -n "$API_PID" ]]; then kill "$API_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

if frontend_is_ours; then
  printf 'Reusing existing frontend at %s; adapter is ready at %s. Press Ctrl-C to stop this launcher.\n' "$WEB_URL" "$API_URL"
  # Keep an adapter started by this script alive for the lifetime of the launcher.
  if [[ -n "$API_PID" ]]; then wait "$API_PID"; else while :; do sleep 3600; done; fi
fi

cd "$ROOT_DIR/frontend"
COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm dev --port "$WEB_PORT"
