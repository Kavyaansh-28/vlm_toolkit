"""Persist reproducible evaluation reports without claiming unrun metrics."""
from __future__ import annotations
import json, platform, sys
from datetime import datetime, timezone
from pathlib import Path

def write_report(result: dict, path: str | Path, configuration: dict, seed: int = 42) -> None:
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "seed": seed,
               "configuration": configuration, "environment": {"python": sys.version, "platform": platform.platform()},
               "results": result}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=2))
