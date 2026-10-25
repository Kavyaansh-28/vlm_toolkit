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
