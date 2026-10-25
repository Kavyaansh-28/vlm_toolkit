from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def save_result(payload: dict[str, Any], path: str = "results/results.json") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        records = json.loads(target.read_text()) if target.exists() else []
        if not isinstance(records, list): records = []
    except (json.JSONDecodeError, OSError):
        records = []
    records.append({"timestamp": datetime.now(timezone.utc).isoformat(), **payload})
    target.write_text(json.dumps(records, indent=2))


def get_device(preference: str = "auto") -> str:
    """Resolve "auto" to cuda, then Apple-Silicon mps, then cpu."""
    if preference and preference != "auto":
        return preference
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"
