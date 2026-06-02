from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .db import get_repo
from .health import get_health
from .ingestion import ingest_events
from .models import IngestRequest, IngestResponse
from .metrics import compute_metrics
from .funnel import compute_funnel
from .heatmap import compute_heatmap
from .anomalies import compute_anomalies
from .pos import POS_CSV_PATH

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("store_intelligence")

app = FastAPI(title="Store Intelligence API", version="1.0.0")

POS_CSV = os.getenv("POS_CSV_PATH", POS_CSV_PATH)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())[:8]
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        '{"trace_id":"%s","endpoint":"%s","method":"%s","latency_ms":%s,"status_code":%s}',
        trace_id, request.url.path, request.method, latency_ms, response.status_code,
    )
    return response


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return get_health()


# ── Ingest ──────────────────────────────────────────────────────────────────

@app.post("/events/ingest", response_model=IngestResponse)
async def ingest(request: Request):
    """
    Accept up to 500 events. Idempotent by event_id.
    Returns 207 if any events were rejected, 200 otherwise.
    Never 5xx for bad event data.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    # Accept either {events:[...]} envelope or a bare list
    if isinstance(body, dict):
        raw_events = body.get("events", [])
    elif isinstance(body, list):
        raw_events = body
    else:
        raise HTTPException(status_code=400, detail="Body must be a JSON object or array")

    if len(raw_events) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds 500 events")

    result = ingest_events(raw_events, repo=get_repo())

    status_code = 207 if result.rejected else 200
    return JSONResponse(content=result.model_dump(), status_code=status_code)


# ── Store endpoints ──────────────────────────────────────────────────────────

def _day_events(store_id: str, date: Optional[str] = None) -> list[dict]:
    """
    Load events for a given UTC day.
    date: "YYYY-MM-DD" string. Defaults to today UTC.
    """
    repo = get_repo()
    if date:
        try:
            day = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day.replace(hour=23, minute=59, second=59)
    return repo.events_for(store_id, start=day, end=day_end)


@app.get("/stores/{store_id}/metrics")
def metrics(store_id: str, date: Optional[str] = None):
    events = _day_events(store_id, date)
    result = compute_metrics(events, POS_CSV)
    result["store_id"] = store_id
    result["date"] = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result["as_of"] = datetime.now(timezone.utc).isoformat()
    return result


@app.get("/stores/{store_id}/funnel")
def funnel(store_id: str, date: Optional[str] = None):
    events = _day_events(store_id, date)
    result = compute_funnel(events, POS_CSV)
    result["store_id"] = store_id
    result["date"] = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result["as_of"] = datetime.now(timezone.utc).isoformat()
    return result


@app.get("/stores/{store_id}/heatmap")
def heatmap(store_id: str, date: Optional[str] = None):
    events = _day_events(store_id, date)
    result = compute_heatmap(events, POS_CSV)
    result["store_id"] = store_id
    result["date"] = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    result["as_of"] = datetime.now(timezone.utc).isoformat()
    return result


@app.get("/stores/{store_id}/anomalies")
def anomalies(store_id: str, date: Optional[str] = None):
    events = _day_events(store_id, date)
    items = compute_anomalies(events, POS_CSV)
    return {
        "store_id": store_id,
        "anomalies": items,
        "count": len(items),
        "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
