from __future__ import annotations

from datetime import datetime, timezone

from .db import get_repo

STALE_THRESHOLD_S = 600


def get_health() -> dict:
    repo = get_repo()
    # Discover all store_ids that have ever sent events
    try:
        with repo._conn() as conn:
            rows = conn.execute(
                "SELECT DISTINCT store_id FROM events"
            ).fetchall()
        store_ids = [r["store_id"] for r in rows]
    except Exception:
        store_ids = []

    stores = {}
    now = datetime.now(timezone.utc)
    for sid in store_ids:
        last_ts = repo.last_event_ts(sid)
        if last_ts is None:
            stores[sid] = {"last_event": None, "lag_s": None, "feed": "STALE_FEED"}
        else:
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            lag_s = (now - last_ts).total_seconds()
            stores[sid] = {
                "last_event": last_ts.isoformat(),
                "lag_s": round(lag_s, 1),
                "feed": "STALE_FEED" if lag_s > STALE_THRESHOLD_S else "LIVE",
            }

    return {"service": "ok", "stores": stores}
