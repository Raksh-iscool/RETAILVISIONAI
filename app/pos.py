from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

IST_OFFSET = timedelta(hours=5, minutes=30)
POS_CSV_PATH = os.getenv("POS_CSV_PATH", "data/pos_transactions.csv")


def load_and_process_pos(csv_path: str = POS_CSV_PATH) -> list[dict]:
    """
    Read POS CSV, filter to genuine sales, collapse to invoices, return list of basket dicts.
    Returns empty list if file missing or unreadable.
    """
    if not os.path.exists(csv_path):
        return []

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return []

    if df.empty:
        return []

    # Normalise column names to lowercase + underscore
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Filter: only SALES invoices
    if "invoice_type" in df.columns:
        df = df[df["invoice_type"].str.strip().str.upper() == "SALES"]

    # Drop returns (return_id not null/empty)
    if "return_id" in df.columns:
        df = df[df["return_id"].isna() | (df["return_id"].astype(str).str.strip() == "")]

    # Filter positive amounts
    amount_col = next((c for c in df.columns if "amount" in c or "total" in c), None)
    if amount_col:
        df = df[pd.to_numeric(df[amount_col], errors="coerce").fillna(0) > 0]

    if df.empty:
        return []

    # Build invoice_number column reference
    inv_col = next((c for c in df.columns if "invoice" in c and "type" not in c), None)
    if not inv_col:
        return []

    # Parse timestamp: try order_date + order_time, else single datetime column
    df = _parse_timestamps(df)
    if "ts_ist" not in df.columns:
        return []

    # Collapse to invoices
    agg: dict = {amount_col: "sum", "ts_ist": "min"}
    if "store_id" in df.columns:
        agg["store_id"] = "first"

    invoices = df.groupby(inv_col).agg(agg).reset_index()
    invoices.rename(columns={inv_col: "invoice_number", amount_col: "total_amount"}, inplace=True)

    # Drop baskets < ₹5 (pure GWP)
    invoices = invoices[invoices["total_amount"] >= 5]

    # Convert IST -> UTC
    def to_utc(ts_ist):
        if pd.isna(ts_ist):
            return None
        if isinstance(ts_ist, datetime):
            return (ts_ist - IST_OFFSET).replace(tzinfo=timezone.utc)
        return None

    invoices["ts_utc"] = invoices["ts_ist"].apply(to_utc)
    invoices = invoices[invoices["ts_utc"].notna()]

    baskets = []
    for _, row in invoices.iterrows():
        baskets.append({
            "invoice_number": str(row["invoice_number"]),
            "ts_utc": row["ts_utc"],
            "value_inr": float(row["total_amount"]),
            "store_id": str(row.get("store_id", "")),
        })
    return baskets


def _parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    date_col = next((c for c in df.columns if "date" in c), None)
    time_col = next((c for c in df.columns if "time" in c), None)

    if date_col and time_col:
        combined = df[date_col].astype(str) + " " + df[time_col].astype(str)
        df["ts_ist"] = pd.to_datetime(combined, errors="coerce", dayfirst=True)
    else:
        dt_col = next((c for c in df.columns if "datetime" in c or "created" in c), None)
        if dt_col:
            df["ts_ist"] = pd.to_datetime(df[dt_col], errors="coerce", dayfirst=True)

    return df


def correlate_conversions(
    baskets: list[dict],
    sessions: list[dict],
    window_s: int = 300,
) -> set:
    """
    Match baskets to non-staff sessions within window_s seconds before basket ts.
    Returns set of converted visitor_ids.
    """
    converted: set = set()
    non_staff = [s for s in sessions if not s.get("is_staff")]

    # Mark sessions as attributed during matching (mutates in place)
    for s in non_staff:
        s.setdefault("_attributed", False)

    window = timedelta(seconds=window_s)

    for basket in baskets:
        bts = _ensure_utc(basket["ts_utc"])
        best: Optional[dict] = None
        best_delta = timedelta.max

        # Primary: billing sessions within window
        for s in non_staff:
            if s.get("_attributed"):
                continue
            billing = s.get("billing")
            if not billing or billing.get("join_ts") is None:
                continue
            jts = _ensure_utc(billing["join_ts"])
            delta = bts - jts
            if timedelta(0) <= delta <= window and delta < best_delta:
                best = s
                best_delta = delta

        # Fallback: any non-staff session whose last event ts is within window
        if best is None:
            for s in non_staff:
                if s.get("_attributed"):
                    continue
                last_ts = _ensure_utc(s.get("exit_ts")) or _last_event_ts(s)
                if last_ts is None:
                    continue
                delta = bts - last_ts
                if timedelta(0) <= delta <= window and delta < best_delta:
                    best = s
                    best_delta = delta

        if best is not None:
            best["_attributed"] = True
            converted.add(best["visitor_id"])

    return converted


def _last_event_ts(session: dict):
    events = session.get("events", [])
    if not events:
        return None
    from .sessions import _ts
    return max(_ts(e) for e in events)


def _ensure_utc(ts):
    if ts is None:
        return None
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts)
        except ValueError:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return None
