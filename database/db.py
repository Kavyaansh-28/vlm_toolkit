from __future__ import annotations
import json, sqlite3
from pathlib import Path

DB = Path("results/experiments.db")
def init():
    DB.parent.mkdir(exist_ok=True); con=sqlite3.connect(DB); con.execute("CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, query TEXT, payload TEXT)"); con.commit(); con.close()
def save(query: str, payload: dict) -> int:
    init(); con=sqlite3.connect(DB); cursor=con.execute("INSERT INTO experiments(query,payload) VALUES (?,?)", (query,json.dumps(payload))); con.commit(); experiment_id = int(cursor.lastrowid); con.close(); return experiment_id
def recent(limit=20):
    init(); con=sqlite3.connect(DB); rows=con.execute("SELECT id,created_at,query,payload FROM experiments ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); con.close(); return rows
