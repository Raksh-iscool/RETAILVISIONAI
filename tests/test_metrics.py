# PROMPT: Test metrics guards — zero events, all-staff events.
# CHANGES MADE: Passes empty POS path to avoid CSV dependency in unit tests.

from app.metrics import compute_metrics


def test_zero_events_no_exception():
    """Zero events → conversion_rate=0.0, status=NO_TRAFFIC, no exception."""
    result = compute_metrics([], pos_csv="nonexistent.csv")
    assert result["conversion_rate"] == 0.0
    assert result["status"] == "NO_TRAFFIC"
    assert result["unique_visitors"] == 0
    assert result["buyers"] == 0


def test_all_staff_events():
    """All events have is_staff=True → unique_visitors=0, conversion_rate=0.0."""
    events = [
        {
            "event_id": "e1",
            "store_id": "ST1008",
            "camera_id": "CAM_01",
            "visitor_id": "STAFF_01",
            "event_type": "ENTRY",
            "timestamp": "2024-01-15T10:00:00+00:00",
            "is_staff": True,
            "confidence": 0.9,
            "dwell_ms": 0,
            "zone_id": None,
        },
        {
            "event_id": "e2",
            "store_id": "ST1008",
            "camera_id": "CAM_01",
            "visitor_id": "STAFF_02",
            "event_type": "ENTRY",
            "timestamp": "2024-01-15T10:01:00+00:00",
            "is_staff": True,
            "confidence": 0.9,
            "dwell_ms": 0,
            "zone_id": None,
        },
    ]
    result = compute_metrics(events, pos_csv="nonexistent.csv")
    assert result["unique_visitors"] == 0
    assert result["conversion_rate"] == 0.0
    assert result["status"] == "NO_TRAFFIC"
