"""
pipeline/emit.py
Build validated Event dicts and POST them to the ingest API.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx


def build_event(
    track_id: int,
    event_type: str,
    store_id: str,
    camera_id: str,
    timestamp: datetime,
    zone_id: Optional[str] = None,
    dwell_ms: int = 0,
    is_staff: bool = False,
    confidence: float = 0.0,
    metadata: Optional[dict] = None,
) -> dict:
    """Build a schema-valid event dict ready for the ingest API."""
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    confidence_band = "HIGH" if confidence >= 0.6 else ("MED" if confidence >= 0.4 else "LOW")

    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": f"{store_id}_T{track_id:04d}",
        "event_type": event_type,
        "timestamp": timestamp.isoformat(),
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": max(0.0, min(1.0, confidence)),
        "metadata": {
            **(metadata or {}),
            "confidence_band": confidence_band,
        },
    }


def post_events(events: list[dict], api_url: str = "http://localhost:8000/events/ingest") -> dict:
    """POST a batch of events to the ingest API. Returns response dict."""
    payload = {"events": events}
    try:
        resp = httpx.post(api_url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        return {"error": str(e), "status_code": e.response.status_code}
    except Exception as e:
        return {"error": str(e)}
