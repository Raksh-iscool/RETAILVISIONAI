"""
pipeline/staff.py
Staff detection via behaviour heuristics.
"""
from __future__ import annotations

import os
from typing import Optional

import yaml

_roster_cache: Optional[list] = None


def _load_roster(path: Optional[str] = None) -> list[str]:
    global _roster_cache
    if _roster_cache is not None:
        return _roster_cache
    cfg_path = path or os.path.join(
        os.getenv("CONFIG_DIR", "config"), "staff_roster.yaml"
    )
    try:
        with open(cfg_path) as f:
            data = yaml.safe_load(f)
        _roster_cache = [s["name"].lower() for s in data.get("staff", [])]
    except Exception:
        _roster_cache = []
    return _roster_cache


def is_staff_by_behaviour(
    zones_visited: int,
    total_dwell_min: float,
    distinct_appearances: int,
) -> bool:
    """
    Heuristic: score >= 2 of 3 signals → classify as staff.
    Signal 1: visited 6+ distinct zones
    Signal 2: total dwell >= 120 minutes
    Signal 3: appeared in 4+ non-contiguous clips/sessions
    """
    score = 0
    if zones_visited >= 6:
        score += 1
    if total_dwell_min >= 120:
        score += 1
    if distinct_appearances >= 4:
        score += 1
    return score >= 2
