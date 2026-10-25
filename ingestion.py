"""Load and normalize modular Rajasthan knowledge documents."""
from __future__ import annotations
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

def load_documents(data_dir: Path = DATA_DIR):
    docs = []
    for path in sorted(data_dir.glob("*")):
        if path.suffix == ".json":
            items = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(items, dict): items = [items]
            for item in items:
                if item.get("text"):
                    item = dict(item)
                    item.setdefault("id", f"{path.stem}-{len(docs)}")
                    item.setdefault("title", item["id"])
                    item.setdefault("destination", "Rajasthan")
                    item.setdefault("category", "general")
                    item.setdefault("source_url", "")
                    item.setdefault("source_type", "local knowledge")
                    item["text"] = " ".join(item["text"].split())
                    # Seed records contain stale/unverifiable social proof and availability.
                    for field in ("rating", "review_count", "top_review", "status"):
                        item.pop(field, None)
                    if item.get("source_type") in {"property knowledge", "restaurant knowledge"}:
                        item["text"] = (f"{item.get('title') or item.get('name', 'Local reference')} in "
                                         f"{item.get('destination', 'Rajasthan')}. Illustrative local reference only; "
                                         "verify current details, prices, hours and availability directly.")
                    docs.append(item)
        elif path.suffix.lower() in {".md", ".txt"}:
            text = " ".join(path.read_text(encoding="utf-8").split())
            if text:
                docs.append({"id": path.stem, "title": path.stem, "destination": "Rajasthan", "category": "general", "text": text, "source_url": "", "source_type": "local document"})
    return docs
