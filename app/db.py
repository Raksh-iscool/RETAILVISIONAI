from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional


DB_PATH = os.getenv("DB_PATH", "data/store_intelligence.db")


def _get_conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class SQLiteRepo:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id   TEXT PRIMARY KEY,
                    store_id   TEXT NOT NULL,
                    camera_id  TEXT NOT NULL,
                    visitor_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ts         TEXT NOT NULL,
                    zone_id    TEXT,
                    dwell_ms   INTEGER DEFAULT 0,
                    is_staff   INTEGER DEFAULT 0,
                    confidence REAL DEFAULT 0.0,
                    payload    TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_store_ts ON events(store_id, ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_store_visitor ON events(store_id, visitor_id)")
            conn.commit()

    def insert_ignore(self, event_dict: dict) -> bool:
        """Returns True if newly inserted, False if duplicate."""
        payload = json.dumps(event_dict.get("metadata", {}))
        try:
            with self._conn() as conn:
                conn.execute(
                    """INSERT OR IGNORE INTO events
                       (event_id, store_id, camera_id, visitor_id, event_type, ts,
                        zone_id, dwell_ms, is_staff, confidence, payload)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        event_dict["event_id"],
                        event_dict["store_id"],
                        event_dict["camera_id"],
                        event_dict["visitor_id"],
                        event_dict["event_type"],
                        event_dict["timestamp"].isoformat() if isinstance(event_dict["timestamp"], datetime)
                        else event_dict["timestamp"],
                        event_dict.get("zone_id"),
                        event_dict.get("dwell_ms", 0),
                        1 if event_dict.get("is_staff") else 0,
                        event_dict.get("confidence", 0.0),
                        payload,
                    ),
                )
                conn.commit()
                return conn.total_changes > 0
        except sqlite3.IntegrityError:
            return False

    def events_for(
        self,
        store_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict]:
        query = "SELECT * FROM events WHERE store_id = ?"
        params: list = [store_id]
        if start:
            query += " AND ts >= ?"
            params.append(start.isoformat())
        if end:
            query += " AND ts <= ?"
            params.append(end.isoformat())
        query += " ORDER BY ts"
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["is_staff"] = bool(d["is_staff"])
            try:
                d["metadata"] = json.loads(d.get("payload") or "{}")
            except Exception:
                d["metadata"] = {}
            ts_str = d["ts"]
            if isinstance(ts_str, str):
                try:
                    d["timestamp"] = datetime.fromisoformat(ts_str)
                except ValueError:
                    d["timestamp"] = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            result.append(d)
        return result

    def last_event_ts(self, store_id: str) -> Optional[datetime]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT ts FROM events WHERE store_id = ? ORDER BY ts DESC LIMIT 1",
                (store_id,),
            ).fetchone()
        if not row:
            return None
        ts_str = row["ts"]
        try:
            return datetime.fromisoformat(ts_str)
        except ValueError:
            return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


_repo: Optional[SQLiteRepo] = None


def get_repo() -> SQLiteRepo:
    global _repo
    if _repo is None:
        _repo = SQLiteRepo(DB_PATH)
    return _repo
