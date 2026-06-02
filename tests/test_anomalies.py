# PROMPT: Test anomaly detection — queue spike CRITICAL, zero events no crash.
# CHANGES MADE: Uses datetime.now UTC for timestamps so queue-depth check (last 5 min) fires correctly.

from datetime import datetime, timedelta, timezone
from app.anomalies import compute_anomalies


def _billing_join(vid, offset_seconds=0):
    ts = (datetime.now(timezone.utc) - timedelta(seconds=offset_seconds)).isoformat()
    return {
        "event_id": f"{vid}-BQ",
        "store_id": "ST1008", "camera_id": "CAM_04",
        "visitor_id": vid, "event_type": "BILLING_QUEUE_JOIN",
        "timestamp": ts, "is_staff": False,
        "confidence": 0.8, "dwell_ms": 0, "zone_id": "BILLING",
        "metadata": {"queue_depth": 1},
    }


def test_billing_queue_spike_critical():
    """8 concurrent BILLING_QUEUE_JOIN events → BILLING_QUEUE_SPIKE with CRITICAL severity."""
    events = [_billing_join(f"V{i:03d}", offset_seconds=i * 5) for i in range(8)]
    anomalies = compute_anomalies(events, pos_csv="nonexistent.csv")
    spike = next((a for a in anomalies if a["type"] == "BILLING_QUEUE_SPIKE"), None)
    assert spike is not None
    assert spike["severity"] == "CRITICAL"
    assert spike["value"] >= 8


def test_zero_events_no_anomalies_no_crash():
    """Zero events → empty anomaly list, no exception."""
    anomalies = compute_anomalies([], pos_csv="nonexistent.csv")
    assert anomalies == []
