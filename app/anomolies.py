from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .sessions import build_sessions, _ts
from .metrics import compute_metrics
from .pos import load_and_process_pos, POS_CSV_PATH

SEVEN_DAY_AVG_PLACEHOLDER = 0.20
QUEUE_WARN_THRESHOLD = 6
QUEUE_CRITICAL_THRESHOLD = 8
CONVERSION_DROP_MIN_VISITORS = 20
DEAD_ZONE_WINDOW_MIN = 60


def compute_anomalies(events: list[dict], pos_csv: str = POS_CSV_PATH) -> list[dict]:
    anomalies: list[dict] = []

    if not events:
        return anomalies

    # ── 1. BILLING_QUEUE_SPIKE ──────────────────────────────────────────────
    current_depth = _current_queue_depth(events)
    if current_depth >= QUEUE_WARN_THRESHOLD:
        severity = "CRITICAL" if current_depth >= QUEUE_CRITICAL_THRESHOLD else "WARN"
        anomalies.append({
            "type": "BILLING_QUEUE_SPIKE",
            "severity": severity,
            "value": current_depth,
            "suggested_action": (
                f"Open second counter - {current_depth} in queue, abandonment risk high"
            ),
        })

    # ── 2. CONVERSION_DROP ──────────────────────────────────────────────────
    metrics = compute_metrics(events, pos_csv)
    unique_visitors = metrics.get("unique_visitors", 0)
    if unique_visitors >= CONVERSION_DROP_MIN_VISITORS:
        today_rate = metrics.get("conversion_rate", 0.0)
        if today_rate < 0.5 * SEVEN_DAY_AVG_PLACEHOLDER:
            today_pct = round(today_rate * 100, 1)
            avg_pct = round(SEVEN_DAY_AVG_PLACEHOLDER * 100, 1)
            anomalies.append({
                "type": "CONVERSION_DROP",
                "severity": "WARN",
                "value": today_rate,
                "suggested_action": (
                    f"Investigate: conversion {today_pct}% vs 7d avg {avg_pct}% "
                    f"- check staffing and stock"
                ),
            })

    # ── 3. DEAD_ZONE ────────────────────────────────────────────────────────
    dead_zones = _dead_zones(events)
    for zone in dead_zones:
        anomalies.append({
            "type": "DEAD_ZONE",
            "severity": "INFO",
            "value": zone,
            "suggested_action": (
                f"Zone {zone} has zero visits - check camera coverage "
                f"or consider re-merchandising"
            ),
        })

    return anomalies


def _current_queue_depth(events: list[dict]) -> int:
    if not events:
        return 0
    latest_ts = max(_ts(e) for e in events)
    cutoff = latest_ts - timedelta(minutes=5)
    in_queue: set[str] = set()
    for e in sorted(events, key=lambda e: _ts(e)):
        if e.get("is_staff"):
            continue
        t = _ts(e)
        if t < cutoff:
            continue
        etype = e["event_type"]
        vid = e["visitor_id"]
        if etype == "BILLING_QUEUE_JOIN":
            in_queue.add(vid)
        elif etype in ("EXIT", "BILLING_QUEUE_ABANDON"):
            in_queue.discard(vid)
    return len(in_queue)


def _dead_zones(events: list[dict]) -> list[str]:
    """Return zone_ids with zero visits in the last DEAD_ZONE_WINDOW_MIN minutes of the event stream."""
    if not events:
        return []

    # Use the latest event timestamp as the reference point (works for both live and historical data)
    latest_ts = max(_ts(e) for e in events)
    cutoff = latest_ts - timedelta(minutes=DEAD_ZONE_WINDOW_MIN)

    try:
        import yaml, os
        cfg_path = os.path.join(os.getenv("CONFIG_DIR", "config"), "store_ST1008.yaml")
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        all_zones = set(cfg.get("zones", {}).keys())
    except Exception:
        all_zones = set()

    if not all_zones:
        return []

    recently_visited: set[str] = set()
    for e in events:
        if e.get("is_staff"):
            continue
        t = _ts(e)
        if t >= cutoff and e.get("zone_id"):
            recently_visited.add(e["zone_id"])

    return sorted(all_zones - recently_visited)
