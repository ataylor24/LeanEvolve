"""
Helpers that choose (parent, operator) pairs using Thompson sampling.
Reuse ProgramDB for records; keep per‑operator success stats in RAM.
"""

from __future__ import annotations
import random, collections
from typing import Dict, List, Tuple, Any
from . import program_db, map_archive as parents_source
import math

NOVEL_ARM = "_NOVEL_"          # constant ID for exploratory slot
P_NOVEL_FLOOR = 0.2           # ensures ≥5 % exploration long‑term

# Memory cache of operator performance {operator_id: [wins, tries]}
_op_stats: Dict[str, List[int]] = collections.defaultdict(lambda: [0, 0])
_op_stats[NOVEL_ARM] = [0, 0]  # bootstrap the novel arm


def update_operator_stats(operator_id: str, reward: float) -> None:
    wins, tries = _op_stats[operator_id]
    _op_stats[operator_id] = [wins + int(reward > 0), tries + 1]


def choose_parents(k: int = 2) -> List[Dict[str, Any]]:
    """Select parents uniformly from current MAP-Elites archive.
    Falls back to legacy ProgramDB if the archive is empty."""
    elites = parents_source.sample_parents(k=k)
    if elites:
        return elites
    # Fallback: Thompson-sample from historical DB
    return program_db.sample_parents(k=k)


def choose_operator(operators: List[str], step: int = 0) -> str:
    """Thompson‑sample across known ops **plus** the '_NOVEL_' arm."""
    all_ops = operators + [NOVEL_ARM]
    draws: List[Tuple[str, float]] = []

    # ε‑greedy style probability floor for NOVEL arm
    epsilon = max(P_NOVEL_FLOOR, 0.25 * math.exp(-step / 5000))
    if random.random() < epsilon:
        return NOVEL_ARM

    for op in all_ops:
        wins, tries = _op_stats.get(op, [0, 0])
        draws.append((op, random.betavariate(wins + 1, tries - wins + 1)))
    draws.sort(key=lambda x: x[1], reverse=True)
    return draws[0][0]
