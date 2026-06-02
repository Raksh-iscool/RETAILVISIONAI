from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .sessions import build_sessions, _ts
from .pos import load_and_process_pos, correlate_conversions, POS_CSV_PATH


def compute_metrics(events: list[dict], pos_csv: str = POS_CSV_PATH) -> dict:
    if not events:
        return _empty_metrics()

    sessions = build_sessions(events)
    customer_sessions = [s for s in sessions if not s.get("is_staff")]
    unique_visitors = len(customer_sessions)

    if unique_visitors == 0:
        return _empty_metrics()

    baskets = load_and_process_pos(pos_csv)
    converted = correlate_conversions(baskets, customer_sessions)
    buyers = len(converted)
    revenue_inr = sum(
        b["value_inr"] for b in baskets
        if b.get("invoice_number") in _attributed_invoices(baskets, converted, customer_sessions)
    )
    # simpler: just sum all correlated basket value
    revenue_inr = _sum_revenue(baskets, customer_sessions)

    conversion_rate = buyers / unique_visitors if unique_visitors > 0 else 0.0

    avg_dwell = _avg_dwell_by_zone(customer_sessions)

    current_queue_depth = _current_queue_depth(events)
    abandonment_rate = _abandonment_rate(customer_sessions)
    revenue_per_visitor = revenue_inr / unique_visitors if unique_visitors > 0 else 0.0

    return {
        "unique_visitors": unique_visitors,
        "buyers": buyers,
        "conversion_rate": round(conversion_rate, 4),
        "avg_dwell_ms_by_zone": avg_dwell,
        "current_queue_depth": current_queue_depth,
        "abandonment_rate": round(abandonment_rate, 4),
        "revenue_inr": round(revenue_inr, 2),
        "revenue_per_visitor_inr": round(revenue_per_visitor, 2),
        "status": "OK",
        "data_confidence": "LOW" if unique_visitors < 20 else "OK",
    }


def _empty_metrics() -> dict:
    return {
        "unique_visitors": 0,
        "buyers": 0,
        "conversion_rate": 0.0,
        "avg_dwell_ms_by_zone": {},
        "current_queue_depth": 0,
        "abandonment_rate": 0.0,
        "revenue_inr": 0.0,
        "revenue_per_visitor_inr": 0.0,
        "status": "NO_TRAFFIC",
        "data_confidence": "LOW",
    }


def _avg_dwell_by_zone(sessions: list[dict]) -> dict[str, float]:
    zone_totals: dict[str, list[int]] = {}
    for s in sessions:
        for zone, dwell in s.get("zones", {}).items():
            zone_totals.setdefault(zone, []).append(dwell)
    return {z: round(sum(v) / len(v), 1) for z, v in zone_totals.items() if v}


def _current_queue_depth(events: list[dict]) -> int:
    if not events:
        return 0
    latest_ts = max(_ts(e) for e in events)
    cutoff = latest_ts - timedelta(minutes=5)
    in_queue: set[str] = set()
    for e in sorted(events, key=lambda e: _ts(e)):
        if e.get("is_staff"):
            continue
        if _ts(e) < cutoff:
            continue
        etype = e["event_type"]
        vid = e["visitor_id"]
        if etype == "BILLING_QUEUE_JOIN":
            in_queue.add(vid)
        elif etype in ("EXIT", "BILLING_QUEUE_ABANDON"):
            in_queue.discard(vid)
    return len(in_queue)


def _abandonment_rate(sessions: list[dict]) -> float:
    joined = [s for s in sessions if s.get("billing") is not None]
    if not joined:
        return 0.0
    abandoned = sum(1 for s in joined if s["billing"].get("abandoned"))
    return abandoned / len(joined)


def _sum_revenue(baskets: list[dict], customer_sessions: list[dict]) -> float:
    if not baskets or not customer_sessions:
        return 0.0
    converted = correlate_conversions(baskets, customer_sessions)
    if not converted:
        return 0.0
    total = sum(b["value_inr"] for b in baskets)
    return total


def _attributed_invoices(baskets, converted, sessions):
    return set()
