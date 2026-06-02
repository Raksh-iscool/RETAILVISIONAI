from __future__ import annotations

from .sessions import build_sessions
from .pos import load_and_process_pos, correlate_conversions, POS_CSV_PATH


def compute_funnel(events: list[dict], pos_csv: str = POS_CSV_PATH) -> dict:
    sessions = build_sessions(events)
    customer_sessions = [s for s in sessions if not s.get("is_staff")]

    stage_entry = [s for s in customer_sessions if s.get("entry_ts") is not None]
    stage_zone = [s for s in customer_sessions if s.get("zones")]
    stage_billing = [s for s in customer_sessions if s.get("billing") and s["billing"].get("join_ts")]

    baskets = load_and_process_pos(pos_csv)
    converted_ids = correlate_conversions(baskets, customer_sessions)
    stage_purchase = [s for s in customer_sessions if s["visitor_id"] in converted_ids]

    counts = [len(stage_entry), len(stage_zone), len(stage_billing), len(stage_purchase)]
    labels = ["stage_entry", "stage_zone_visit", "stage_billing", "stage_purchase"]

    stages = {}
    for i, label in enumerate(labels):
        prev = counts[i - 1] if i > 0 else counts[0]
        drop_off = round((prev - counts[i]) / prev * 100, 1) if prev > 0 and i > 0 else 0.0
        stages[label] = {"count": counts[i], "drop_off_from_previous_pct": drop_off}

    return {"stages": stages, "total_sessions": len(customer_sessions)}
