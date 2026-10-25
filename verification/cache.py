"""Append-only JSONL cache for visual-verifier outputs.

Detector boxes/scores and region-probe probabilities are cached per image
content hash, so benchmark outputs can be reprocessed with new thresholds,
weights or ablations without loading any model (``cache_only``).
"""
from __future__ import annotations

import hashlib
import json
import threading
from functools import lru_cache
from pathlib import Path


class CacheMiss(RuntimeError):
    """Raised in cache-only mode when a verifier output was never computed."""


# Verification cost accounting: every verifier output records the time it took to
# compute (model loading excluded); cache hits add that stored time back, so the
# latency of a reprocessed or ablated run equals the real (first-pass) cost.
_COST = {"ms": 0.0}


def reset_cost() -> None:
    _COST["ms"] = 0.0


def add_cost(ms: float) -> None:
    _COST["ms"] += float(ms or 0.0)


def cost_ms() -> float:
    return _COST["ms"]


@lru_cache(maxsize=4096)
def _hash(path: str, mtime: float) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_sha256(path: str) -> str:
    return _hash(str(path), Path(path).stat().st_mtime)


class VerificationCache:
    def __init__(self, path: str | Path | None, cache_only: bool = False):
        self.path = Path(path) if path else None
        self.cache_only = cache_only
        self._data: dict[str, dict] = {}
        self._lock = threading.Lock()
        if self.path and self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        row = json.loads(line)
                        self._data[row["key"]] = row
                    except (json.JSONDecodeError, KeyError):
                        continue

    def get(self, key: str) -> dict | None:
        row = self._data.get(key)
        if row is None and self.cache_only:
            raise CacheMiss(f"No cached verifier output for {key}")
        return row

    def put(self, key: str, value: dict) -> None:
        row = {"key": key, **value}
        with self._lock:
            self._data[key] = row
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row) + "\n")
