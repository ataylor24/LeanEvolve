from __future__ import annotations

"""MAP-Elites-inspired archive for Lean-Conjecturer.

This module maintains a map from *behaviour-descriptor* bins (a.k.a. islands)
onto *elite* records.  Each bin stores (at most) the single best-fitness
conjecture discovered so far that falls inside that bin.

Public API (see docstrings below):
    init_archive(cfg: MapConfig) -> None
    clear_elites() -> None
    update_elites(entry: dict) -> None
    sample_parents(k: int) -> list[dict]
    get_all_elites() -> list[dict]
    persist() -> None
    load_existing() -> None

Legacy helpers (read-only):
    append_legacy(entry: dict) -> str
    load_legacy(min_score) -> list[dict]

The implementation tries to be *very* lightweight; it keeps the archive in
process memory and writes the entire structure out as one smallish JSON file
upon `persist()`.  For our current workloads this is perfectly adequate (<<1 MB).
"""

import json
import random
import time
import uuid
import pathlib
import threading
from typing import Dict, Tuple, List, Any

from .map_config import MapConfig
from . import program_db  # for append_legacy / load_legacy
from src.entity.mutation import Mutation

# ---------------------------------------------------------------------------
# Globals – intentionally simple
# ---------------------------------------------------------------------------

_cfg: MapConfig | None = None
_elite_map: Dict[Tuple[int, ...], Dict[str, Any]] = {}
_dirty: bool = False  # set when we need to re-persist
_lock = threading.Lock()  # coarse, in-process lock only


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(v, hi))


def _feature_key(entry: Dict[str, Any]) -> Tuple[int, ...] | None:
    """Return the discrete MAP-Elites bin indices for *entry*.

    Returns `None` when required dimensions are missing or malformed;
    caller should then skip the update.
    """
    global _cfg
    assert _cfg is not None, "Archive not initialised"

    features = entry.get("map_scores", {})
    if not features:
        return tuple([0.0] * 4)
    indices: List[int] = []
    for dim in _cfg.dims:
        val = features.get(dim)
        if val is None or not isinstance(val, (int, float)):
            # invalid feature – skip this entry with a warning
            print(
                f"[map_archive] Warning: missing/invalid feature '{dim}' in entry; skipping…"
            )
            continue
        # clamp NaNs, infinities, etc.
        try:
            score_f = float(val)
        except Exception:
            print(
                f"[map_archive] Warning: could not convert feature '{dim}' to float; skipping…"
            )
            score_f = 0.0
        if score_f != score_f:  # NaN check
            print(
                f"[map_archive] Warning: feature '{dim}' is NaN; skipping…"
            )
            score_f = 0.0
        score_f = max(0.0, min(score_f, 100.0))  # clamp to [0,100]
        n_bins = _cfg.bins[dim]
        idx = _clamp(int((score_f / 100.0) * n_bins), 0, n_bins - 1)
        indices.append(idx)

    return tuple(indices)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_archive(cfg: MapConfig | None = None) -> None:
    """Initialise the in-memory archive and, if present, load the persisted map.

    Clients should call this exactly once at the start of a run.
    """
    global _cfg, _elite_map, _dirty
    if _cfg is not None:
        return  # already initialised

    _cfg = cfg or MapConfig()

    # ensure parent directory exists
    path = pathlib.Path(_cfg.file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    _elite_map.clear()
    _dirty = False
    load_existing()


def clear_all_elites() -> None:
    """Drop *all* current elites from memory (optionally between iterations)."""
    global _elite_map, _dirty
    _elite_map.clear()
    _dirty = True


def prune_underperformers() -> None:
    """Remove elites that fall below the configured fitness threshold or are stale.

    Uses MapConfig.prune_threshold (absolute on entry['fitness_score']) and
    MapConfig.stale_after_sec relative to entry['timestamp'].
    """
    global _elite_map, _cfg, _dirty
    assert _cfg is not None, "Archive not initialised"
    if not _elite_map:
        return
    now_ts = int(time.time())
    threshold = float(getattr(_cfg, "prune_threshold", 0.0))
    staleness = int(getattr(_cfg, "stale_after_sec", 0))
    to_delete = []
    for key, rec in _elite_map.items():
        score = float(rec.get("fitness_score", 0.0))
        ts = int(rec.get("timestamp", 0))
        is_under = score < threshold
        is_stale = staleness > 0 and (now_ts - ts) >= staleness
        if is_under or is_stale:
            to_delete.append(key)
    if to_delete:
        for k in to_delete:
            _elite_map.pop(k, None)
        _dirty = True
        print(f"[map_archive] Pruned {len(to_delete)} underperforming/stale elites")


def update_elites(entry: Dict[str, Any]) -> None:
    """Possibly insert *entry* into its bin if it out-performs the incumbent."""
    global _elite_map, _dirty

    if "fitness_score" not in entry:
        print("[map_archive] Warning: entry without 'fitness_score' – skipping…")
        return

    # ensure IDs and timestamps present (mirrors program_db.append semantics)
    entry.setdefault("id", str(uuid.uuid4()))
    entry.setdefault("timestamp", int(time.time()))

    key = _feature_key(entry)
    if key is None:
        return

    new_score = entry["fitness_score"]
    incumbent = _elite_map.get(key)

    replaced = False
    if incumbent is None:
        replaced = True
    else:
        inc_score = incumbent.get("fitness_score", float("-inf"))
        if new_score > inc_score:
            replaced = True
        elif new_score == inc_score and entry["timestamp"] > incumbent.get("timestamp", 0):
            replaced = True

    if replaced:
        _elite_map[key] = entry
        _dirty = True
        print(
            f"[map_archive] Elite update @{key}: score {incumbent and incumbent.get('fitness_score')} -> {new_score}"
        )


def get_all_elites() -> List[Dict[str, Any]]:
    return list(_elite_map.values())

def get_elite_mutations() -> List[Mutation]:
    return [Mutation(**elite) for elite in get_all_elites()]

def sample_parents(k: int = 2) -> List[Dict[str, Any]]:
    elites = get_all_elites()
    if not elites:
        return []
    if len(elites) <= k:
        return elites.copy()
    return random.sample(elites, k)


def persist() -> None:
    """Write the current archive to `file_path` if there were changes."""
    global _dirty, _cfg
    if not _dirty:
        return

    path = pathlib.Path(_cfg.file_path)

    # --- write to temporary then rename for atomicity ----------------------
    data_to_save = {",": "."}  # placeholder to avoid empty file confusion
    data_to_save = {
        ",".join(map(str, key)): rec for key, rec in _elite_map.items()
    }

    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

    tmp_path.rename(path)
    _dirty = False


def load_existing() -> None:
    """Load archive from disk (if any) into `_elite_map`."""
    global _elite_map, _cfg
    path = pathlib.Path(_cfg.file_path)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        for k_str, rec in data.items():
            try:
                key = tuple(int(x) for x in k_str.split(","))
            except ValueError:
                print(f"[map_archive] Warning: bad key in archive file: {k_str!r}")
                continue
            _elite_map[key] = rec
    except Exception as e:
        print(f"[map_archive] Failed to load archive: {e}")


# ---------------------------------------------------------------------------
# Back-compat helpers – just delegate to program_db -------------------------
# ---------------------------------------------------------------------------

def append_legacy(entry: Dict[str, Any]) -> str:
    """Forward-compat wrapper for audit trail recording using the JSONL DB."""
    return program_db.append(entry)


def load_legacy(min_score: float = 0.0):
    return program_db.load(min_score=min_score)
