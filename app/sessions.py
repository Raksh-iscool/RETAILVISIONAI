from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

MAX_DWELL_PER_EVENT_MS = 600_000  # 10 minutes


def build_sessions(events: list[dict]) -> list[dict]:
    """
    Group events into per-visitor sessions.
    REENTRY reuses the existing session — does NOT create a second visitor.
    Sticky staff: any is_staff=True event taints the whole session.
    Returns all sessions; callers must filter is_staff.
    """
    sorted_events = sorted(events, key=lambda e: _ts(e))

    sessions: dict[str, dict] = {}  # visitor_id -> session

    clip_end: Optional[datetime] = None
    for e in sorted_events:
        t = _ts(e)
        if clip_end is None or t > clip_end:
            clip_end = t

    for e in sorted_events:
        vid = e["visitor_id"]
        etype = e["event_type"]
        t = _ts(e)

        if vid not in sessions:
            sessions[vid] = {
                "visitor_id": vid,
                "store_id": e.get("store_id", ""),
                "entry_ts": None,
                "exit_ts": None,
                "exit_inferred": False,
                "zones": {},          # zone_id -> total dwell_ms
                "billing": None,
                "events": [],
                "is_staff": False,
                "confs": [],
            }

        sess = sessions[vid]

        # Sticky staff
        if e.get("is_staff"):
            sess["is_staff"] = True

        sess["confs"].append(e.get("confidence", 0.0))
        sess["events"].append(e)

        if etype == "ENTRY":
            if sess["entry_ts"] is None:
                sess["entry_ts"] = t

        elif etype == "REENTRY":
            # Same visitor — keep existing session, update entry_ts only if unset
            if sess["entry_ts"] is None:
                sess["entry_ts"] = t

        elif etype == "EXIT":
            sess["exit_ts"] = t

        elif etype in ("ZONE_ENTER", "ZONE_DWELL"):
            zone = e.get("zone_id")
            if zone:
                raw_dwell = e.get("dwell_ms", 0)
                capped = min(raw_dwell, MAX_DWELL_PER_EVENT_MS)
                sess["zones"][zone] = sess["zones"].get(zone, 0) + capped

        elif etype == "ZONE_EXIT":
            pass  # dwell already captured via ZONE_DWELL events

        elif etype == "BILLING_QUEUE_JOIN":
            if sess["billing"] is None:
                sess["billing"] = {
                    "join_ts": t,
                    "depth": e.get("metadata", {}).get("queue_depth") if isinstance(e.get("metadata"), dict)
                              else getattr(e.get("metadata"), "queue_depth", None),
                    "abandoned": False,
                    "attributed": False,
                }

        elif etype == "BILLING_QUEUE_ABANDON":
            if sess["billing"] is not None:
                sess["billing"]["abandoned"] = True

    # Close dangling sessions (no EXIT recorded)
    for sess in sessions.values():
        if sess["exit_ts"] is None:
            sess["exit_ts"] = clip_end
            sess["exit_inferred"] = True
        # Ensure entry_ts is set if we only have zone/dwell events
        if sess["entry_ts"] is None and sess["events"]:
            sess["entry_ts"] = _ts(sess["events"][0])

    return list(sessions.values())


def _ts(event: dict) -> datetime:
    ts = event.get("timestamp") or event.get("ts")
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts)
        except ValueError:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return datetime.now(timezone.utc)
