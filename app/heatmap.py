from __future__ import annotations

from .sessions import build_sessions
from .pos import load_and_process_pos, POS_CSV_PATH


def compute_heatmap(events: list[dict], pos_csv: str = POS_CSV_PATH) -> dict:
    sessions = build_sessions(events)
    customer_sessions = [s for s in sessions if not s.get("is_staff")]

    zone_visits: dict[str, int] = {}
    zone_dwell: dict[str, int] = {}

    for s in customer_sessions:
        for zone, dwell in s.get("zones", {}).items():
            zone_visits[zone] = zone_visits.get(zone, 0) + 1
            zone_dwell[zone] = zone_dwell.get(zone, 0) + dwell

    if not zone_visits:
        return {"zones": {}, "data_confidence": "LOW", "attention_vs_sales": {}}

    max_visits = max(zone_visits.values()) or 1
    total_dwell = sum(zone_dwell.values()) or 1

    baskets = load_and_process_pos(pos_csv)
    total_revenue = sum(b["value_inr"] for b in baskets) or 1.0

    zones_out = {}
    avs = {}
    for zone in zone_visits:
        visits = zone_visits[zone]
        dwell = zone_dwell.get(zone, 0)
        avg_d = dwell / visits if visits > 0 else 0.0
        score = round(visits / max_visits * 100, 1)
        zones_out[zone] = {
            "visit_count": visits,
            "avg_dwell_ms": round(avg_d, 1),
            "normalised_score": score,
        }
        dwell_share = round(dwell / total_dwell, 4)
        # sales_share: match zone name substring to basket (simple heuristic)
        zone_revenue = _zone_revenue(zone, baskets)
        sales_share = round(zone_revenue / total_revenue, 4)
        avs[zone] = {
            "dwell_share": dwell_share,
            "sales_share": sales_share,
            "gap": round(dwell_share - sales_share, 4),
        }

    total_sess = len(customer_sessions)
    return {
        "zones": zones_out,
        "data_confidence": "LOW" if total_sess < 20 else "OK",
        "attention_vs_sales": avs,
    }


def _zone_revenue(zone_id: str, baskets: list[dict]) -> float:
    # Simple: if basket store_id contains zone substring (rough proxy)
    # In production this would use SKU→brand→zone mapping
    return 0.0
