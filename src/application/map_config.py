from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple


@dataclass
class MapConfig:
    """Configuration for MAP-Elites style archive.

    dims
        Ordered list of feature names we use for binning.
    bins
        Mapping feature -> number of bins.  Every feature **must** appear here.
    reset_each_iter
        Whether to clear all elites at the beginning of every pipeline iteration.
        Setting this to *True* gives an \u201cisland* evolutionary set-up whereas
        *False* produces the classic accumulating MAP-Elites archive.
    file_path
        Where to persist the archive on disk.  A single JSON document mapping
        "n_idx,d_idx,depth_idx" (comma-separated integers) to the elite record.
    """

    dims: Tuple[str, ...] = ("novelty", "difficulty", "depth", "provability_estimate")
    bins: Dict[str, int] = field(
        default_factory=lambda: {
            "novelty": 10,
            "difficulty": 10,
            "depth": 10,
            "provability_estimate": 10,
        }
    )
    reset_each_iter: bool = False
    file_path: str = "data/program_map.json"
    # Pruning configuration: drop elites below this fitness threshold and
    # optionally prune if an elite has not been updated for `stale_after_sec`.
    prune_threshold: float = 0.0   # keep all by default
    stale_after_sec: int = 0       # 0 disables staleness pruning

    def __post_init__(self) -> None:
        # basic validation
        missing = [d for d in self.dims if d not in self.bins]
        if missing:
            raise ValueError(f"bins missing entries for dims: {missing}")
