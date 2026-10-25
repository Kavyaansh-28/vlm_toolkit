"""SQLite audit log (paper Sec. IV-E: image hash, candidates, claim scores, action taken)
plus human annotations of flagged claims."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "results" / "experiments.db"


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, query TEXT, payload TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS annotations (id INTEGER PRIMARY KEY, experiment_id INTEGER, claim_id TEXT, label TEXT, note TEXT, "
                "created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(experiment_id, claim_id))")
    return con


def init() -> None:
    _connect().close()


def save(query: str, payload: dict) -> int:
    with _connect() as con:
        cursor = con.execute("INSERT INTO experiments(query,payload) VALUES (?,?)", (query, json.dumps(payload)))
        return int(cursor.lastrowid)


def recent(limit: int = 20) -> list[tuple]:
    with _connect() as con:
        return con.execute("SELECT id,created_at,query,payload FROM experiments ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def get(experiment_id: int) -> tuple | None:
    with _connect() as con:
        return con.execute("SELECT id,created_at,query,payload FROM experiments WHERE id=?", (experiment_id,)).fetchone()


def save_annotation(experiment_id: int, claim_id: str, label: str, note: str = "") -> None:
    with _connect() as con:
        con.execute("INSERT INTO annotations(experiment_id,claim_id,label,note) VALUES (?,?,?,?) "
                    "ON CONFLICT(experiment_id, claim_id) DO UPDATE SET label=excluded.label, note=excluded.note, created_at=CURRENT_TIMESTAMP",
                    (experiment_id, claim_id, label, note))


def flagged_claims(limit: int = 200) -> list[dict]:
    """Claims the policy flagged (ABSTAIN) on selected candidates, with any human label."""
    with _connect() as con:
        labels = {(row[0], row[1]): (row[2], row[3]) for row in
                  con.execute("SELECT experiment_id, claim_id, label, note FROM annotations")}
    items = []
    for experiment_id, created_at, query, payload in recent(200):
        data = json.loads(payload)
        for candidate in data.get("candidates", []):
            if not candidate.get("selected", True):
                continue
            claims = {c["id"]: c for c in candidate.get("claims", [])}
            evidence = {e["claim_id"]: e for e in candidate.get("evidence", [])}
            for claim_id, action in (candidate.get("claim_actions") or {}).items():
                if action != "ABSTAIN" or claim_id not in claims:
                    continue
                claim, ev = claims[claim_id], evidence.get(claim_id, {})
                label, note = labels.get((experiment_id, claim_id), (None, ""))
                items.append({"experiment_id": experiment_id, "created_at": created_at, "query": query,
                              "candidate_id": candidate.get("id"), "claim_id": claim_id, "claim": claim,
                              "claim_text": _describe(claim), "sentence": claim.get("text", ""),
                              "v": (candidate.get("claim_values") or {}).get(claim_id), "status": ev.get("status"),
                              "explanation": ev.get("explanation", ""), "region_crop": ev.get("region_crop"),
                              "label": label, "note": note})
                if len(items) >= limit:
                    return items
    return items


def _describe(claim: dict) -> str:
    kind, subject, value = claim.get("type"), claim.get("subject"), claim.get("value")
    if kind == "attribute": return f"{subject} is {value}"
    if kind == "quantity": return f"{value} × {subject}"
    if kind == "relation": return f"{subject} {str(value).replace('_', ' ')} {claim.get('object')}"
    return f"{subject} exists"
