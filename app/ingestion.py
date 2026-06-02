from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from .db import SQLiteRepo, get_repo
from .models import Event, IngestResponse, RejectedEvent


def ingest_events(raw_events: list[Any], repo: SQLiteRepo | None = None) -> IngestResponse:
    if repo is None:
        repo = get_repo()

    ingested = 0
    duplicates = 0
    rejected: list[RejectedEvent] = []

    for i, raw in enumerate(raw_events):
        event_id_hint = raw.get("event_id") if isinstance(raw, dict) else None
        try:
            event = Event.model_validate(raw)
        except ValidationError as exc:
            rejected.append(RejectedEvent(index=i, error=str(exc), event_id=event_id_hint))
            continue
        except Exception as exc:
            rejected.append(RejectedEvent(index=i, error=f"Unexpected: {exc}", event_id=event_id_hint))
            continue

        event_dict = event.model_dump()
        inserted = repo.insert_ignore(event_dict)
        if inserted:
            ingested += 1
        else:
            duplicates += 1

    return IngestResponse(ingested=ingested, duplicates=duplicates, rejected=rejected)
