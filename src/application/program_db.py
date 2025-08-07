"""
Append‑only JSONL “database” for Lean‑Conjecturer Alpha‑Evolve prototype.
Each line = one JSON dict recording a conjecture attempt.

API
---
append(entry: dict)        -> None
load(min_score: float=0.0) -> list[dict]
sample_parents(k: int = 2) -> list[dict]
"""

from __future__ import annotations
import json, uuid, pathlib, random, time
from typing import List, Dict, Any

DB_FILE = pathlib.Path("data/program_db.jsonl")
DB_FILE.parent.mkdir(parents=True, exist_ok=True)


def _jsonl_reader() -> List[Dict[str, Any]]:
    if not DB_FILE.exists():
        return []
    with DB_FILE.open() as f:
        return [json.loads(line) for line in f]


def append(entry: Dict[str, Any]) -> str:
    """Append a single record (dict) to the JSONL file."""
    id = str(uuid.uuid4())
    entry.setdefault("id", id)
    entry.setdefault("timestamp", int(time.time()))
    with DB_FILE.open("a") as f:               # append‑mode keeps file valid JSONL:contentReference[oaicite:0]{index=0}
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return id

def load(min_score: float = 0.0) -> List[Dict[str, Any]]:
    """Load all records with score ≥ min_score into memory."""
    return [r for r in _jsonl_reader() if r.get("score", 0.0) >= min_score]  # filter keeps RAM small


def sample_parents(k: int = 2) -> List[Dict[str, Any]]:
    """
    Thompson‑sampling over historical success rates.
    Score must lie in [0, 1].  Draw β(score+1, 2‑score) for each record and take top‑k.:contentReference[oaicite:1]{index=1}
    """
    records = load()
    if not records:
        return []
    beta_draws = [
        (r, random.betavariate(r["score"] + 1, 2 - r["score"]))
        for r in records
    ]
    beta_draws.sort(key=lambda x: x[1], reverse=True)
    return [r for r, _ in beta_draws[:k]]
