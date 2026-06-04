# 📦 RETAILVISIONAI — The Complete Guide

> One document to understand everything, run everything, debug everything.
> Written so a complete beginner can follow it, but precise enough that an engineer can ship from it.

---

## Table of Contents

1. [What Is This?](#1-what-is-this)
2. [The North Star Metric](#2-the-north-star-metric)
3. [How Data Flows Through the System](#3-how-data-flows-through-the-system)
4. [Every Folder and File Explained](#4-every-folder-and-file-explained)
5. [Setup: From Zero to a Running API](#5-setup-from-zero-to-a-running-api)
6. [Running the CCTV Detection Pipeline](#6-running-the-cctv-detection-pipeline)
7. [The Dashboard — A Visual Tour](#7-the-dashboard--a-visual-tour)
8. [Every API Endpoint with Real Examples](#8-every-api-endpoint-with-real-examples)
9. [Understanding the Output Numbers](#9-understanding-the-output-numbers)
10. [How Every Number Is Calculated](#10-how-every-number-is-calculated)
11. [All 50 Edge Cases and How They Were Solved](#11-all-50-edge-cases-and-how-they-were-solved)
12. [Running Tests and Checking Coverage](#12-running-tests-and-checking-coverage)
13. [Debugging Common Errors](#13-debugging-common-errors)
14. [Daily-Use Command Cheat Sheet](#14-daily-use-command-cheat-sheet)
15. [Links and References](#15-links-and-references)

---

## 1. What Is This?

Imagine you own a beauty store on Brigade Road, Bangalore. Hundreds of customers walk in every day. You want to know things like:

- **How many real people walked in?** (not staff, not the same person twice)
- **Out of those, how many actually bought something?**
- **Which shelf do people spend the most time near?**
- **Is there a long queue at the billing counter right now?**
- **Where am I losing customers between "browse" and "buy"?**

E-commerce companies have known the answers to these questions for 20 years. Physical stores still ask cashiers at end-of-day "how was today?" and call that analytics.

**This system fixes that.** It watches your existing CCTV cameras, figures out who is a customer vs who is staff, tracks them through the store, matches what they did with what they bought at the cash register, and gives you a dashboard that updates in real time.

The simple story:

```
CCTV cameras  ──►  AI detects people  ──►  Tracks them across frames
                                              │
                                              ▼
                                       Builds "sessions"
                                       (one visit = one session)
                                              │
                                              ▼
                                  Matches sessions to POS receipts
                                              │
                                              ▼
                            Shows you the dashboard at localhost:8000
```

---

## 2. The North Star Metric

Every architectural decision in this code is judged against **one number**:

```
                    Number of buyers
Conversion rate  =  ─────────────────────────────
                    Number of unique non-staff visitors
```

That's it. Everything else — the heatmap, the funnel, the anomalies — exists to _explain_ this number when it moves.

**Why this number is hard to get right:**

| Mistake                                   | What it does to the number                                 |
| ----------------------------------------- | ---------------------------------------------------------- |
| Count raw ENTRY events                    | Overstates visitors by 30-40× (one person → 40 detections) |
| Count visitor_ids without merging REENTRY | Overstates by ~15% (every re-entrant double-counted)       |
| Forget to filter `is_staff=True`          | Understates conversion (staff in denominator)              |
| Count POS line items as conversions       | Overstates by 4× (101 line items vs 24 invoices)           |
| Use POS times in IST instead of UTC       | Zeros all correlations (5h30m off)                         |
| Treat "Guest" name as a dedup key         | Loses 30% of buyers                                        |

This guide documents how each of these mistakes is prevented in the code.

---

## 3. How Data Flows Through the System

```
┌───────────────────────────────────────────────────────────────────────────┐
│ INPUT                                                                     │
│  5 CCTV mp4 files     +    Brigade Bangalore POS CSV (101 line items)     │
└──────────────┬──────────────────────────────────────┬─────────────────────┘
               │                                      │
               ▼                                      │
   ┌────────────────────────┐                         │
   │ DETECTION PIPELINE     │                         │
   │ (scripts/run_pipeline) │                         │
   │                        │                         │
   │ ▸ YOLOv8n finds people │                         │
   │ ▸ ByteTrack assigns IDs│                         │
   │ ▸ Zone polygons label  │                         │
   │   where each person is │                         │
   │ ▸ Edge cases applied:  │                         │
   │   group entry,         │                         │
   │   re-entry trap,       │                         │
   │   reflection drop,     │                         │
   │   sticky staff, ...    │                         │
   │ ▸ POST events to API   │                         │
   └──────────────┬─────────┘                         │
                  │                                   │
                  ▼                                   │
   ┌──────────────────────────────────────┐           │
   │ API: POST /events/ingest             │           │
   │ ▸ Validates with Pydantic            │           │
   │ ▸ Inserts into SQLite                │           │
   │   (idempotent on event_id)           │           │
   └──────────────┬───────────────────────┘           │
                  │                                   │
                  ▼                                   ▼
   ┌──────────────────────────────────────────────────────────┐
   │ ANALYTICS (read time, derived from raw events)           │
   │                                                          │
   │  sessions.py    → group events by visitor_id             │
   │  pos.py         → collapse 101 line items → 24 invoices  │
   │  metrics.py     → conversion_rate, dwell, queue, revenue │
   │  funnel.py      → entry → zone → billing → purchase      │
   │  heatmap.py     → dwell share vs sales share gap         │
   │  anomalies.py   → queue spike, conversion drop, dead zone│
   └──────────────┬───────────────────────────────────────────┘
                  │
                  ▼
   ┌──────────────────────────────────────────────────────────┐
   │ DASHBOARD (localhost:8000)                               │
   │                                                          │
   │ ▸ Live MJPEG video with detection overlays               │
   │ ▸ Real-time metric cards (SSE updates every 2s)          │
   │ ▸ Conversion funnel with drop-off %                      │
   │ ▸ Zone heatmap showing dwell-vs-sales gap                │
   │ ▸ Alerts panel with operational suggested_actions        │
   │ ▸ Store report — generate, download CSV/JSON             │
   └──────────────────────────────────────────────────────────┘
```

---

## 4. Every Folder and File Explained

```
store-intelligence/
│
├── 📄 README.md              Quick-start with 5 commands
├── 📄 GUIDE.md               THIS FILE — complete reference
├── 📄 Dockerfile             Recipe for the container image
├── 📄 docker-compose.yml     One-command startup
├── 📄 requirements.txt       All Python dependencies
├── 📄 .env.example           Template for environment variables
│
├── 📁 app/                   API server (FastAPI)
│   ├── main.py               All endpoints + dashboard routes + SSE streams
│   ├── models.py             What an Event looks like (Pydantic) + confidence bands
│   ├── db.py                 SQLite read/write — the only file that touches the DB
│   ├── ingestion.py          Validates and stores incoming event batches
│   ├── sessions.py           Groups raw events into visitor sessions
│   ├── pos.py                POS CSV loader + invoice collapse + IST→UTC + correlation
│   ├── metrics.py            Conversion rate, dwell time, queue depth, revenue
│   ├── funnel.py             4-stage funnel: entry → zone → billing → purchase
│   ├── heatmap.py            Per-zone dwell-share vs sales-share gap
│   ├── anomalies.py          Queue spike, conversion drop, dead zone alerts
│   ├── health.py             /health endpoint with LIVE / STALE_FEED
│   ├── stream.py             MJPEG video stream generator with YOLO overlays
│   └── static/
│       └── index.html        The dashboard UI (Purplle-branded)
│
├── 📁 pipeline/              Vision pipeline (turns video into events)
│   ├── detect.py             YOLOv8n person detection
│   ├── tracker.py            ByteTrack — assigns stable IDs across frames
│   ├── zones.py              Ray-cast point-in-polygon for zone assignment
│   ├── staff.py              Staff detection (uniform, behaviour, roster, cashier)
│   ├── edge_cases.py         EC-1, 2, 3, 5, 7, 8, 9, 19, 20 detection guards
│   ├── reid.py               EC-12, 13, 14, 15, 16 re-identification
│   ├── crosscam.py           EC-17, 18 cross-camera deduplication
│   ├── emit.py               Builds events and POSTs them to /events/ingest
│   └── run.sh                Wrapper script for processing one video file
│
├── 📁 scripts/               Helper scripts
│   ├── run_pipeline.py       MASTER SCRIPT — process all 5 cameras
│   ├── probe_videos.py       Check video metadata (fps, size, duration)
│   ├── save_frames.py        Save sample frames as JPG for visual inspection
│   └── analyze_pos.py        Validate POS CSV parses correctly (24 invoices check)
│
├── 📁 config/                Store-specific configuration
│   ├── store_ST1008.yaml     Zone polygons, camera roles, brand→zone map
│   └── staff_roster.yaml     Names of known staff members
│
├── 📁 data/                  All data files
│   ├── sample_events.jsonl   20 sample events for manual testing
│   ├── pos_transactions.csv  Synthetic POS data (24 invoices)
│   ├── Brigade_Bangalore_10_April_26.csv  REAL Purplle POS data (101 → 24)
│   ├── store_intelligence.db SQLite database (auto-created)
│   └── cctv/                 Your CCTV footage goes here
│       └── CCTV Footage/     ← 5 MP4 files from the challenge
│
├── 📁 tests/                 Automated tests (144 total)
│   ├── test_ingestion.py     HTTP ingest idempotency
│   ├── test_ingest_http.py   EC-44 (idempotency), EC-45 (partial success)
│   ├── test_sessions.py      REENTRY dedup, sticky staff
│   ├── test_metrics.py       Empty store, all-staff guards
│   ├── test_funnel.py        Funnel monotonicity, REENTRY in funnel
│   ├── test_anomalies.py     Queue spike CRITICAL, zero events no crash
│   ├── test_pipeline_edges.py All 20 detection/tracking/re-ID EC tests
│   ├── test_pos_edges.py     All 16 POS/session EC tests (24-basket assert)
│   ├── test_heatmap_health.py Zone aggregation, STALE_FEED detection
│   └── test_analytics.py     Brand heatmap, real anomalies, structured logging
│
└── 📁 docs/                  Design documentation
    ├── DESIGN.md             Architecture, sessions-as-truth, AI decisions
    ├── CHOICES.md            3 load-bearing decisions with rationale
    └── DECISIONS.log         30 line-per-decision audit log
```

---

## 5. Setup: From Zero to a Running API

### Option A: Docker (recommended — zero local Python install needed)

**Step 1.** Install Docker Desktop from <https://www.docker.com/products/docker-desktop>. After install, you'll see a whale icon in your taskbar.

**Step 2.** Clone the repo and start everything:

```bash
git clone <your-repo-url> store-intelligence
cd store-intelligence
docker compose up --build -d
```

**Step 3.** Wait ~10 seconds for the container to start, then verify:

```bash
curl http://localhost:8000/health
```

You should see:

```json
{ "service": "ok", "checked_at_utc": "...", "stores": {} }
```

**Step 4.** Open the dashboard:

```
http://localhost:8000/
```

That's the entire acceptance gate. **No further setup is needed.**

---

### Option B: Local Python (for development)

**Step 1.** Make sure you have Python 3.10 or 3.11:

```bash
python --version
```

If you don't, download from <https://www.python.org/downloads/>.

**Step 2.** Install dependencies:

```bash
cd store-intelligence
pip install -r requirements.txt
```

This installs FastAPI, ultralytics (YOLOv8), pandas, OpenCV, pytest, and everything else.

**Step 3.** Set environment variables.

**PowerShell (Windows):**

```powershell
$env:DB_PATH = "data/store_intelligence.db"
$env:CONFIG_DIR = "config"
$env:POS_CSV_PATH = "data/pos_transactions.csv"
```

**Bash (Mac/Linux):**

```bash
export DB_PATH=data/store_intelligence.db
export CONFIG_DIR=config
export POS_CSV_PATH=data/pos_transactions.csv
```

**Step 4.** Start the API:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

You'll see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

**Step 5.** Verify with another terminal:

```bash
curl http://127.0.0.1:8000/health
```

---

## 6. Running the CCTV Detection Pipeline

The pipeline reads the 5 CCTV videos, runs YOLOv8 detection + ByteTrack tracking, applies all 20 detection edge cases, and POSTs structured events to `/events/ingest`.

**Pre-flight check** — confirm all 5 videos are readable:

```bash
python scripts/probe_videos.py
```

Expected output:

```
CAM_01: 1920x1080  fps=30.0  frames=4193  dur=2.3min  size=180MB  readable=True
CAM_02: 1920x1080  fps=30.0  frames=3774  dur=2.1min  size=162MB  readable=True
CAM_03: 1920x1080  fps=30.0  frames=4436  dur=2.5min  size=191MB  readable=True
CAM_04: 1920x1080  fps=25.0  frames=3647  dur=2.4min  size=73MB   readable=True
CAM_05: 1920x1080  fps=25.0  frames=3465  dur=2.3min  size=73MB   readable=True
```

**Run the full pipeline** — processes all 5 cameras (takes ~3-5 minutes on a modern CPU):

```bash
python scripts/run_pipeline.py --api http://127.0.0.1:8000 --skip-frames 8
```

Expected output:

```
CAM_01 (product_zone):  26 tracks,  75 events posted
CAM_02 (product_zone):  45 tracks, 247 events posted
CAM_03 (entry_exit):     0 tracks,  16 crossing events
CAM_04 (staff_only):     0 tracks,   0 events
CAM_05 (billing):       21 tracks,  42 events
─────────────────────────────────────────────────
TOTAL:                  92 tracks, 380 events posted
```

**Flag reference:**

| Flag                   | What it does                                      | Default                 |
| ---------------------- | ------------------------------------------------- | ----------------------- |
| `--api URL`            | Where to POST events                              | `http://localhost:8000` |
| `--dry-run`            | Don't POST — just count                           | `false`                 |
| `--skip-frames N`      | Process every (N+1)th frame. 8 = ~4fps from 30fps | `5`                     |
| `--cameras CAM_01 ...` | Which cameras to process                          | all 5                   |

**Common usage patterns:**

```bash
# Quick validation that detection works (no DB writes)
python scripts/run_pipeline.py --cameras CAM_03 --dry-run --skip-frames 15

# Just the entry camera, dense sampling (more accurate)
python scripts/run_pipeline.py --cameras CAM_03 --skip-frames 2

# Re-run all 5 cameras (idempotent — duplicates auto-ignored)
python scripts/run_pipeline.py --skip-frames 8
```

After the pipeline finishes, query the API with the footage date `2026-04-10`:

```bash
curl "http://127.0.0.1:8000/stores/ST1008/metrics?date=2026-04-10"
```

---

## 7. The Dashboard — A Visual Tour

Open `http://localhost:8000/` (or `http://localhost:8000/dashboard/`).

The page has **two views** controlled by the tab in the top right:

### Live Operations View

**Band 1 — Key Metric Cards (4 cards)**

| Card               | Shows                        | Updates from           |
| ------------------ | ---------------------------- | ---------------------- |
| Today's Conversion | e.g. `1.08%`                 | `/api/live` SSE stream |
| Unique Visitors    | e.g. `93`                    | same stream            |
| Revenue Today      | e.g. `₹35,716`               | same stream            |
| Queue Now          | e.g. `0` (red + pulse if ≥6) | same stream            |

**Band 2 — Detection Feed + Alerts**

The left 60% shows a **live MJPEG video stream** from one camera with bounding boxes drawn in real time:

- Each tracked person gets a coloured box with their track ID
- Zone polygons (LAKME, FACES_CANADA, etc.) are drawn semi-transparent
- Entry line on CAM_03 shown dashed
- Camera role badge top-left, detection count bottom-left

Below the main camera, two thumbnails show CAM_03 (Entry) and CAM_05 (Billing). Click any camera button to switch.

The right 38% shows the **Alerts panel** with cards for:

- `CRITICAL` (red) — billing queue ≥ 8
- `WARN` (amber) — conversion drop, queue ≥ 6
- `INFO` (purple) — dead zone, coverage gap

**Band 3 — Zone Performance Table**

Each row: zone name, dwell share bar, revenue share bar, assessment.

- `↑ Review placement` if dwell exceeds revenue by 10%
- `✓ Balanced` otherwise

### Store Report View

A date picker + "Generate Report" button. Click → spinner → renders a clean, printable report with:

1. Summary header (store, date)
2. 4-stat snapshot row (conversion, visitors, revenue, avg basket)
3. Customer journey funnel
4. Zone performance table
5. Alerts raised today

**Download buttons** — CSV or JSON, both pull from live data.

---

## 8. Every API Endpoint with Real Examples

All endpoints run at `http://localhost:8000`. Open `http://localhost:8000/docs` for an interactive Swagger UI.

### `GET /health`

Reports per-store feed status. Use this for monitoring/alerts.

```bash
curl http://localhost:8000/health
```

```json
{
  "service": "ok",
  "checked_at_utc": "2026-06-02T15:09:31+00:00",
  "stores": {
    "ST1008": {
      "last_event_utc": "2026-04-10T14:42:28+00:00",
      "lag_seconds": 4577314.8,
      "feed": "STALE_FEED"
    }
  }
}
```

- `feed: "LIVE"` if the last event was less than 10 minutes ago
- `feed: "STALE_FEED"` if older — the camera might be down

### `POST /events/ingest`

Receives events from the pipeline. **Idempotent on `event_id`** — sending the same event_id twice is a no-op.

```bash
curl -X POST http://localhost:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "events": [{
      "event_id":"my-unique-id-001",
      "store_id":"ST1008",
      "camera_id":"CAM_03",
      "visitor_id":"V001",
      "event_type":"ENTRY",
      "timestamp":"2026-04-10T08:00:00+00:00",
      "confidence":0.85
    }]
  }'
```

```json
{ "ingested": 1, "duplicates": 0, "rejected": [] }
```

- `HTTP 200` — all events accepted
- `HTTP 207` — some events rejected (others were stored)
- `HTTP 400` — entire request body is invalid JSON
- **Never returns 5xx for bad event data** — that's a business error, not a server error

### `GET /stores/{store_id}/metrics`

The core dashboard payload. Add `?date=YYYY-MM-DD` for historical data.

```bash
curl "http://localhost:8000/stores/ST1008/metrics?date=2026-04-10"
```

```json
{
  "unique_visitors": 93,
  "buyers": 1,
  "conversion_rate": 0.0108,
  "avg_dwell_ms_by_zone": {
    "LAKME": 99142.1, "GOOD_VIBES": 147240.2, ...
  },
  "current_queue_depth": 0,
  "abandonment_rate": 0.0,
  "revenue_inr": 35715.5,
  "revenue_per_visitor_inr": 384.04,
  "status": "OK",
  "data_confidence": "OK",
  "session_confidence_distribution": {"HIGH": 6, "MEDIUM": 85, "LOW": 2},
  "metrics_pending_late_events": false
}
```

### `GET /stores/{store_id}/funnel`

The 4-stage conversion funnel.

```bash
curl "http://localhost:8000/stores/ST1008/funnel?date=2026-04-10"
```

```json
{
  "stages": {
    "stage_entry": { "count": 93, "drop_off_from_previous_pct": 0.0 },
    "stage_zone_visit": { "count": 57, "drop_off_from_previous_pct": 38.7 },
    "stage_billing": { "count": 14, "drop_off_from_previous_pct": 75.4 },
    "stage_purchase": { "count": 1, "drop_off_from_previous_pct": 92.9 }
  },
  "total_sessions": 93
}
```

Reading this: 93 walked in → 38.7% left without browsing → 75.4% browsed but never reached billing → 92.9% reached billing but didn't buy. **Biggest leak is the browse-to-billing gap.**

### `GET /stores/{store_id}/heatmap`

Per-zone visit counts, dwell, and the dwell-vs-sales gap (Purplle's unique R&D signal).

```bash
curl "http://localhost:8000/stores/ST1008/heatmap?date=2026-04-10"
```

```json
{
  "zones": {
    "LAKME": {"visit_count": 18, "avg_dwell_ms": 99142.1, "normalised_score": 100.0,
              "status": "ACTIVE", "data_confidence": "OK"},
    "DERMdoc": {"visit_count": 0, "status": "UNKNOWN_NO_COVERAGE", ...}
  },
  "attention_vs_sales": {
    "LAKME": {"dwell_share": 0.26, "sales_share": 0.0, "gap": 0.26,
              "interpretation": "HIGH_ATTENTION_LOW_SALES"},
    "DERMdoc": {"dwell_share": 0.0, "sales_share": 0.86, "gap": -0.86,
                "interpretation": "LOW_ATTENTION_HIGH_SALES"}
  }
}
```

| Interpretation             | Meaning                                                    |
| -------------------------- | ---------------------------------------------------------- |
| `HIGH_ATTENTION_LOW_SALES` | People hover here but don't buy → re-merchandise candidate |
| `LOW_ATTENTION_HIGH_SALES` | Efficient sales without much browsing                      |
| `BALANCED`                 | Dwell roughly matches revenue                              |

### `GET /stores/{store_id}/anomalies`

Three anomaly types with **operational suggested_actions**:

```bash
curl "http://localhost:8000/stores/ST1008/anomalies?date=2026-04-10"
```

```json
{
  "anomalies": [
    {
      "type": "BILLING_QUEUE_SPIKE",
      "severity": "CRITICAL",
      "value": 9,
      "threshold": 8,
      "suggested_action": "URGENT: 9 in billing queue. Open counter 2 immediately and alert floor manager."
    },
    {
      "type": "CONVERSION_DROP",
      "severity": "WARN",
      "value": 0.05,
      "suggested_action": "Conversion 5.0% vs 7d avg 20.0%. Check: staffing levels, stock availability, AC/environment."
    },
    {
      "type": "DEAD_ZONE",
      "severity": "INFO",
      "value": "MINIMALIST",
      "suggested_action": "Zone 'MINIMALIST' has zero visitors for 60+ min. Action: check camera view is unobstructed; if confirmed dead -> consider re-merchandising."
    },
    {
      "type": "COVERAGE_GAP",
      "severity": "INFO",
      "value": "DERMdoc",
      "suggested_action": "Zone 'DERMdoc' has no camera coverage - dwell data unavailable."
    }
  ]
}
```

`DEAD_ZONE` and `COVERAGE_GAP` are intentionally different anomalies — one means "rethink the placement", the other means "fix the camera".

### `GET /dashboard/stream/{store_id}`

Server-Sent Events stream. Emits one event every 2 seconds. Used by the dashboard.

```bash
curl -N "http://localhost:8000/dashboard/stream/ST1008"
```

```
data: {"conversion_rate": 0.0108, "unique_visitors": 93, "buyers": 1, "current_queue_depth": 0, "revenue_inr": 35715.5, "ts_utc": "2026-06-02T15:12:11Z"}

data: {"conversion_rate": 0.0108, ...}
```

### `GET /api/live`

Richer SSE stream — emits metrics + anomalies + heatmap + funnel every 3 seconds.

### `GET /stream/{camera_id}`

MJPEG video stream with detection overlays. View directly in a browser:

```
http://localhost:8000/stream/CAM_01
```

Or embed in HTML: `<img src="/stream/CAM_01">`.

### `GET /events/recent?store_id=ST1008&limit=40`

Returns the most recent N events for the live event-feed panel.

### `GET /reports/export?store_id=ST1008&date=2026-04-10&format=json`

Downloads a full report. `format` can be `json` or `csv`.

---

## 9. Understanding the Output Numbers

### From the real Brigade Bangalore footage (10 April 2026, 2.5 min per camera):

```
unique_visitors: 93              ← 93 distinct people walked in
buyers:           1              ← only 1 matched a POS invoice
conversion_rate: 1.08%           ← 1/93 = 1.08%

Why so low?
The footage is a 2.5-minute window during a busy evening.
POS data is for the full day (24 invoices, ₹35,716 revenue).
Correlation only finds the buyers whose visit overlaps the 2.5-min window.
On a full-day clip, you'd expect 15-20% conversion.

Top zones by visits:
  LAKME:         18 visits  avg 99 sec
  FACES_CANADA:  15 visits  avg 64 sec
  GOOD_VIBES:    12 visits  avg 147 sec  ← longest dwell — high "consider" intent
  THE_FACE_SHOP:  2 visits  avg 31 sec   ← almost ignored
  MINIMALIST:     0 visits             ← DEAD_ZONE flagged

Anomalies fired:
  COVERAGE_GAP — NY_BAE, DERMdoc      (camera doesn't see them)
  DEAD_ZONE    — MINIMALIST            (camera sees it, but nobody goes)

Confidence distribution:
  HIGH:    6 sessions
  MEDIUM: 85 sessions
  LOW:     2 sessions   ← clearly readable bar in dashboard
```

---

## 10. How Every Number Is Calculated

### Conversion rate

```
unique_visitors  = count of build_sessions(events) where is_staff == False
buyers           = count of sessions matched to POS invoices via attribute_txn()
conversion_rate  = buyers / unique_visitors    (guarded — returns 0.0 if denominator is 0)
```

### Dwell time per zone

```python
for each session:
    for each ZONE_DWELL event in session:
        capped = min(dwell_ms, 600_000)        # 10-min cap per event
        zone_dwell[zone_id] += capped

avg_dwell_ms[zone] = sum_of_capped_dwell / count_of_visiting_sessions
```

### Funnel drop-off

```
drop_off_pct = (prev_stage_count - this_stage_count) / prev_stage_count × 100
```

Each stage uses `set(visitor_id)` (never event counts). The set at stage N is a subset of stage N-1 → funnel is monotonically decreasing.

### Queue depth

Look at the last 5 minutes of footage. Track who joined queue (`BILLING_QUEUE_JOIN`) minus those who exited (`EXIT`, `BILLING_QUEUE_ABANDON`). The remaining set's size = queue depth.

### Attention vs sales gap

```
dwell_share[z]  = zone_dwell[z]      / sum_of_zone_dwell
sales_share[z]  = zone_revenue[z]    / total_revenue
gap[z]          = dwell_share - sales_share
```

| `gap`     | Interpretation           |
| --------- | ------------------------ |
| `> +0.10` | HIGH_ATTENTION_LOW_SALES |
| `< -0.10` | LOW_ATTENTION_HIGH_SALES |
| otherwise | BALANCED                 |

### CONVERSION_DROP anomaly

```
7d_avg = average conversion_rate from daily_stats over last 7 days
         (only rows where unique_visitors >= 20, excluding today)

fires if:
    today_conversion < 7d_avg × 0.6
    AND today_unique_visitors >= 20
    AND 7d_avg > 0  (i.e. baseline exists)
```

---

## 11. All 50 Edge Cases and How They Were Solved

This is the complete catalogue. Each EC has: the problem, the file, the function, and a one-line explanation of the solution.

### Group A — Detection & Counting (`pipeline/edge_cases.py`)

**EC-1 — Group entry**
_Problem:_ Three people walk in at once. Naive logic counts them as 1 blob = 1 entry.
_Solution:_ `EntryExitCounter.update(track_id, feet_y)` is called **per track**, not per detection blob. Each track has its own crossing state. 8px hysteresis prevents oscillation around the line.
_Test:_ 3 simultaneous tracks crossing downward → exactly 3 ENTRY events.

**EC-2 — Tailgating merged box**
_Problem:_ Two close customers detected as one wide bounding box.
_Solution:_ `split_merged_box(box, single_person_w)` splits if box width > 1.8× normal OR IoU with a nearby box > 0.55. Returns 2 boxes down the middle.

**EC-3 — Doorway loiter**
_Problem:_ Person hovers in the doorway oscillating above/below the entry line → generates phantom ENTRY/EXIT events.
_Solution:_ `net_direction(y_history, line_y, min_net=25)` requires net displacement ≥25px. Pure oscillation never counts.

**EC-5 — Door swing phantoms**
_Problem:_ Glass door swing creates 1-frame ghost detections.
_Solution:_ `crossing_is_real(track_age_frames, min_age=4)` — track must be at least 4 frames old before a crossing counts. Phantoms die in 1-2 frames.

**EC-7 — Mannequin / standee**
_Problem:_ A standee or mannequin is detected as a person, never moves, but counts as a visitor.
_Solution:_ `is_static_prop(positions, px_thresh=6)` — if 30+ position records all fall within 6px diagonal, classify as static prop and suppress.

**EC-8 — Glass reflections**
_Problem:_ Reflections in glass doors detected as people standing inside the store.
_Solution:_ `drop_reflection(bbox, glass_masks)` — feet-point ray-cast against `glass_mask_polygons` from config. Detection dropped if feet fall inside a mask.

**EC-9 — Shadows**
_Problem:_ Long shadow on the floor detected as a person.
_Solution:_ `looks_like_shadow(bbox, conf)` — flat aspect ratio (0.25–0.65) AND confidence < 0.20 = shadow.

**EC-19 — Boundary exit**
_Problem:_ Person walks behind a display shelf at the frame edge — we lose them but they didn't actually exit the store.
_Solution:_ `is_boundary_exit(bbox, frame_w, frame_h, pad=12)` — if any bbox edge is within 12px of frame edge, park in LostTrackBuffer instead of emitting EXIT.

**EC-20 — Sticky staff label**
_Problem:_ Staff member momentarily looks like a customer (sits down, removes uniform jacket) → label flips.
_Solution:_ `sticky_staff(track_state, tid, frame_is_staff, conf, lock_conf=0.8)` — once classified staff at conf ≥ 0.8, lock the label permanently.

### Group B — Re-Identification (`pipeline/reid.py`)

**EC-12 — Re-entry gallery**
_Problem:_ Customer leaves and re-enters 8 minutes later. ByteTrack has forgotten them → new visitor_id, double-counted.
_Solution:_ `ReIDGallery(window_s=900, sim_thr=0.62)` stores exit embeddings for 15 minutes. On new entry, cosine-similarity match against gallery → re-entry inherits the original visitor_id.

**EC-13 — The 3-second trap (THE critical one)**
_Problem:_ Door guard leaves and re-enters in 3 seconds. Two different people also enter 3 seconds apart. Timing alone cannot distinguish them.
_Solution:_ `reentry_decision(exit_embed, entry_embed, gap_s)` — **appearance similarity is the SOLE arbiter**. If cosine sim ≥ 0.62 → REENTRY regardless of gap. If sim < 0.62 and gap < 2s → NEW_VISITOR. Timing is only a hint for gallery pruning.
_Tests:_ (a) same person, sim=0.97, gap=30s → REENTRY. (b) different people, sim=0.0, gap=3s → NEW_VISITOR.

**EC-14 — Embed drift**
_Problem:_ Lighting changes throughout the day, customer's stored embedding becomes stale.
_Solution:_ `update_running_embed(running, new_embed, alpha=0.1)` — exponential moving average keeps the gallery fresh.

**EC-15 — Clothing collision**
_Problem:_ Two people wearing similar colours get merged across cameras.
_Solution:_ `feasible_match(last_pos, last_ts, cand_pos, cand_ts, max_speed_px_s=600)` — reject re-ID if implied speed exceeds human walking speed.

**EC-16 — Lost track buffer**
_Problem:_ Customer ducks behind a display unit. ByteTrack assigns a new track_id when they reappear.
_Solution:_ `LostTrackBuffer(ttl_frames=45)` parks vanished tracks for 1.5s (45 frames @ 30fps). On reappearance, cosine match reclaims the original track_id.

**EC-17/18 — Cross-camera continuity**
_Problem:_ Customer walks from CAM_01's view into CAM_02's view → gets a new visitor_id.
_Solution:_ `crosscam_inherit(gallery, embed, ts)` — shared `ReIDGallery` across all cameras. New entry on any camera first queries the gallery.
_EC-18 zone ownership:_ `owns_detection(camera_id, zone_id, zone_camera_map)` — only the owning camera emits events for overlap zones. Prevents double-counting dwell.

### Group C — Staff Detection (`pipeline/staff.py`)

**EC-21 — Uniform match**
_Solution:_ `uniform_match(torso_hist, uniform_ref_hist, thr=0.7)` — colour histogram intersection ≥ 0.7.

**EC-22 — Cashier detection**
_Problem:_ The cashier permanently stationed at the billing counter would otherwise count as being "in queue".
_Solution:_ `is_cashier(zone_id, dwell_ms, behind_counter)` — in BILLING zone, dwell ≥ 50% of 20 min, and behind the counter polygon → cashier, excluded from queue depth.

**EC-24 — Roster cross-check**
_Solution:_ `roster_is_staff(name)` — loads names from `config/staff_roster.yaml`, normalises case+whitespace. Names: kasthuri v, zufishan khazra, shashikala, naziya begum, priya v.

**EC-25 — Behaviour score**
_Solution:_ `staff_behaviour_score(zones_visited, total_dwell_min, distinct_visits)` — score ≥ 2 of 3 signals (zones≥6, dwell≥120min, visits≥4) → classify as staff.

### Group E — POS & Billing Correctness (`app/pos.py`)

**EC-34 — Closest unattributed correlation**
_Solution:_ `correlate_txn_to_session(txn_ts, billing_sessions, window_s=300)` — among billing sessions whose `join_ts` is in the 5-min window before `txn_ts`, pick the closest. Mark attributed=True so it can't match a second invoice.

**EC-35 — Multi-item basket = ONE conversion** ⭐ THE BIG ONE
_Problem:_ Brigade CSV has 101 line items. Naive count → 101 conversions. Reality → 24 invoices = 24 conversions.
_Solution:_ `baskets_from_pos(rows)` groups by `invoice_number`, sums amounts, takes earliest order_time as basket ts. **Asserted by test:** `len(baskets) == 24` against the real CSV. If anyone ever regresses this loader, the test fails loudly.

**EC-36 — Guest checkout**
_Problem:_ 20 of 101 rows have `customer_name = "Guest"`. Identity-based dedup would merge unrelated buyers.
_Solution:_ `usable_identity(name, phone)` returns `None` for "Guest", "anonymous", "walk-in". Conversion correlation never relies on identity — only time-window + billing-zone presence.

**EC-37 — Unique buyers**
_Solution:_ `unique_buyers(baskets)` — distinct usable identities (case-normalised name) + each Guest counts as 1 separate buyer. We do NOT merge anonymous baskets.

**EC-38 — Mobile POS fallback**
_Problem:_ A salesperson uses a mobile POS device — the customer never appears on the billing camera.
_Solution:_ `attribute_txn(txn_ts, billing_sessions, all_sessions)` — first tries billing-window match (EC-34). If no match, falls back to closest non-staff session whose last event is within the window. Returns `(visitor_id, method)` where method is `"billing"` or `"last_zone_fallback"`.

**EC-39 — Filter returns and non-sales**
_Solution:_ `is_real_sale(row)` — must have `invoice_type=="sales"`, no `return_id`, and `total_amount > 0`.

**EC-40 — Pure GWP / ₹1 baskets**
_Solution:_ `is_meaningful_basket(basket, floor=5.0)` — basket value must be ≥ ₹5. Drops pure gift-with-purchase invoices.

**EC-42 — Clock skew estimation**
_Problem:_ Camera clock and POS clock may drift apart.
_Solution:_ `estimate_clock_offset(billing_minute_hist, txn_minute_hist, max_shift=10)` — cross-correlate the two histograms by shifting one ±10 minutes. The shift maximising product-sum is the estimated offset.

**EC-49 — IST → UTC at the boundary** ⭐ Another critical one
_Problem:_ A 5h30m off-by-default silently zeros all POS correlation.
_Solution:_ `pos_local_to_utc(date_str, time_str)` — the ONE place in the codebase where IST is converted to UTC. All downstream code is pure UTC.
_Test:_ `pos_local_to_utc("10-04-2026", "16:55:36")` → `2026-04-10T11:25:36+00:00`.

### Group F — Session & Time (`app/sessions.py`, `app/main.py`)

**EC-41 — Dangling sessions at clip end**
_Solution:_ `close_dangling_sessions(open_sessions, clip_end_ts)` — any session with `exit_ts == None` gets `exit_ts = clip_end_ts` and `exit_inferred = True`.

**EC-43 — Out-of-order / late events**
_Solution:_ `within_watermark(event_ts, now, grace_s=30)` + `has_late_events(events, grace_s=5)`. The `/metrics` response sets `metrics_pending_late_events: true` when events arrive late.

**EC-44 — HTTP idempotency**
_Solution:_ `INSERT OR IGNORE` on `event_id`. Test: POST identical event twice in **separate** HTTP calls → second returns `duplicates=1, ingested=0`, DB has exactly 1 row.

**EC-45 — Partial-success structured errors**
_Solution:_ Batch of 5 events with index-2 and index-4 invalid → HTTP 207, `rejected: [{index:2, error:"confidence..."}, {index:4, error:"store_id..."}]`. Valid events still ingest.

**EC-46/47 — Empty store + all-staff guard**
_Solution:_ `compute_metrics([])` and `compute_metrics(all_staff_events)` both return `{status:"NO_TRAFFIC", conversion_rate:0.0, ...}`. No NaN anywhere, no exception.

### EC-50 — Confidence calibration (`app/models.py`)

_Solution:_ `confidence_band(conf)`:

- `HIGH` if conf ≥ 0.70
- `MEDIUM` if 0.40 ≤ conf < 0.70
- `LOW` if conf < 0.40

`session_confidence(event_confs)` averages then bands. Exposed in `/metrics` and `/funnel` responses as `session_confidence_distribution`. **Low-confidence detections are never dropped** — they're flagged.

### Funnel-specific edge case

_Problem:_ A REENTRY visitor would naively count twice in stage_entry.
_Solution:_ `compute_funnel` uses `set(visitor_id)` for each stage. Stage N's set is the intersection of all prior stages → monotonically decreasing, asserted with `assert counts[i] <= counts[i-1]`.

### Heatmap-specific edge cases

- **Single-session dwell cap** (`capped_zone_dwell`, cap=600,000 ms = 10 min) — prevents one makeup trial from dominating the heatmap.
- **Zone status disambiguation:** `UNKNOWN_NO_COVERAGE` for zones without a camera (declared in config), `DEAD_ZONE` for covered zones with zero visits in 60 min, `ACTIVE` otherwise.
- **COVERAGE_GAP vs DEAD_ZONE anomaly** — distinct types so managers don't confuse "fix the camera" with "rethink the placement".

---

## 12. Running Tests and Checking Coverage

```bash
# Quick test run
python -m pytest tests/ -v

# With coverage report
python -m pytest tests/ --cov=app --cov=pipeline --cov-report=term-missing

# Specific test class
python -m pytest tests/test_pos_edges.py::TestEC35MultiItemBasket -v

# Just the 3-second trap test (EC-13)
python -m pytest tests/ -k "three_second" -v
```

**Expected output:**

```
============================= 144 passed in 4.02s =============================
```

**Coverage breakdown (the targets):**

| Module                                                                     | Coverage | Status                                     |
| -------------------------------------------------------------------------- | -------- | ------------------------------------------ |
| `app/funnel.py`                                                            | 100%     | ✓                                          |
| `app/heatmap.py`                                                           | 100%     | ✓                                          |
| `app/models.py`                                                            | 92%      | ✓                                          |
| `app/anomalies.py`                                                         | 90%      | ✓                                          |
| `app/db.py`                                                                | 86%      | ✓                                          |
| `app/ingestion.py`                                                         | 85%      | ✓                                          |
| `app/pos.py`                                                               | 81%      | ✓                                          |
| `app/metrics.py`                                                           | 80%      | ✓                                          |
| `app/health.py`                                                            | 79%      | ✓                                          |
| `app/sessions.py`                                                          | 78%      | ✓                                          |
| `pipeline/edge_cases.py`                                                   | 94%      | ✓                                          |
| `pipeline/reid.py`                                                         | 96%      | ✓                                          |
| `pipeline/staff.py`                                                        | 64%      | unit-tested where possible                 |
| `app/main.py`                                                              | 48%      | HTTP routes (covered by live verification) |
| `app/stream.py`, `pipeline/detect.py`, `tracker.py`, `zones.py`, `emit.py` | 0%       | Video/GPU — verified by live pipeline run  |

**The 24-baskets assertion test** (the one that would catch the #1 failure mode):

```bash
python -m pytest tests/test_pos_edges.py::TestEC35MultiItemBasket::test_brigade_csv_exactly_24_baskets -v
```

This asserts `len(load_and_process_pos(BRIGADE_CSV)) == 24` against the real CSV.

---

## 13. Debugging Common Errors

### ❌ "No module named 'ultralytics'"

```bash
pip install ultralytics
```

### ❌ "No module named 'pytest'" or "pytest-cov"

```bash
pip install pytest pytest-cov httpx
```

### ❌ "Cannot open video" / "0 tracks detected"

**Cause 1 — wrong path:**

```bash
python scripts/probe_videos.py
# Verify all 5 cameras show readable=True
```

**Cause 2 — too many frames skipped:**

```bash
python scripts/run_pipeline.py --cameras CAM_03 --skip-frames 2  # denser sampling
```

### ❌ "Connection refused" when running the pipeline

The API server isn't running. Start it in a separate terminal first:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### ❌ Metrics return `status: "NO_TRAFFIC"` after running the pipeline

The footage is dated **10 April 2026** but you queried today's date. Always add `?date=2026-04-10`:

```bash
curl "http://127.0.0.1:8000/stores/ST1008/metrics?date=2026-04-10"
```

### ❌ `unique_visitors` is unexpectedly high

The tracker is losing people between frames. Lower the skip:

```bash
python scripts/run_pipeline.py --skip-frames 2
```

### ❌ Staff appearing in customer metrics

Check `config/store_ST1008.yaml`:

```yaml
camera_roles:
  CAM_04: staff_only
```

And verify CAM_04 has actual detections:

```bash
python scripts/run_pipeline.py --cameras CAM_04 --dry-run
```

### ❌ `docker compose up` fails with "port 8000 already in use"

Stop the conflicting process or change the port in `docker-compose.yml`:

```yaml
ports:
  - "8001:8000" # change 8001 to any free port
```

### ❌ Database has stale data, want a fresh start

```powershell
# Windows PowerShell
Stop-Process -Name python -Force
Remove-Item data\store_intelligence.db
```

```bash
# Mac/Linux
pkill -f uvicorn
rm data/store_intelligence.db
```

The database is auto-created on the next API start.

### ❌ "bytetrack.yaml not found"

```bash
pip install --upgrade ultralytics
```

### ❌ Tests fail with `ModuleNotFoundError` for `app` package

You're running from the wrong directory. cd to project root:

```bash
cd store-intelligence
python -m pytest tests/ -v
```

### ❌ Dashboard SSE shows "Disconnected"

Check the API is reachable from your browser console (F12):

```javascript
fetch("/health")
  .then((r) => r.json())
  .then(console.log);
```

If that fails, the dashboard can't reach the API — usually a docker-compose port mapping issue.

### Where to look when something goes wrong

```
Problem                          → File / Command to check
────────────────────────────────────────────────────────────────
API won't start                  → pip install -r requirements.txt
                                   python -m uvicorn app.main:app

Events not saving                → DB_PATH env var; data/ folder writable

Wrong metrics                    → Add ?date=YYYY-MM-DD to URL
                                   curl /health → see "last_event_utc"

No people detected               → scripts/probe_videos.py
                                   --skip-frames 2

Duplicate visitor IDs            → Lower --skip-frames
                                   ByteTrack persist=True must be on

Staff counted as customers       → config/store_ST1008.yaml camera_roles

Zone data missing                → config/store_ST1008.yaml zones polygons
                                   scripts/save_frames.py → inspect visually

Tests fail after change          → pytest --tb=long  (full traceback)

Coverage below 70%               → pytest --cov=app --cov-report=term-missing
                                   Look at "Missing" column

Dashboard shows nothing          → Browser F12 console
                                   curl /api/live (SSE endpoint)
```

---

## 14. Daily-Use Command Cheat Sheet

```bash
# ─── Setup (once) ──────────────────────────────────────────────
pip install -r requirements.txt

# ─── Start the API ─────────────────────────────────────────────
# PowerShell
$env:DB_PATH="data/store_intelligence.db"
$env:CONFIG_DIR="config"
$env:POS_CSV_PATH="data/pos_transactions.csv"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Or with Docker
docker compose up -d

# ─── Open the dashboard ────────────────────────────────────────
# http://localhost:8000/        ← main dashboard
# http://localhost:8000/docs    ← interactive Swagger UI

# ─── Process the CCTV footage ──────────────────────────────────
python scripts/run_pipeline.py --api http://127.0.0.1:8000 --skip-frames 8

# ─── Query the analytics ───────────────────────────────────────
curl "http://127.0.0.1:8000/stores/ST1008/metrics?date=2026-04-10"
curl "http://127.0.0.1:8000/stores/ST1008/funnel?date=2026-04-10"
curl "http://127.0.0.1:8000/stores/ST1008/heatmap?date=2026-04-10"
curl "http://127.0.0.1:8000/stores/ST1008/anomalies?date=2026-04-10"

# ─── Send sample events ────────────────────────────────────────
curl -X POST http://127.0.0.1:8000/events/ingest \
  -H "Content-Type: application/json" \
  -d @data/sample_events.jsonl

# ─── Test ──────────────────────────────────────────────────────
python -m pytest tests/ -v
python -m pytest tests/ --cov=app --cov=pipeline --cov-report=term-missing

# ─── Probe video files ─────────────────────────────────────────
python scripts/probe_videos.py
python scripts/save_frames.py    # saves data/cctv/frames/*.jpg

# ─── Check the 24-basket assertion (the big one) ───────────────
python -m pytest tests/test_pos_edges.py::TestEC35MultiItemBasket -v

# ─── Fresh start (wipe DB) ─────────────────────────────────────
# Windows: Remove-Item data\store_intelligence.db
# Mac/Linux: rm data/store_intelligence.db

# ─── Stop everything ───────────────────────────────────────────
# Windows: Stop-Process -Name python -Force
# Docker:  docker compose down
```

---

## 15. Links and References

### Technologies Used

| Tool             | Purpose               | Link                                        |
| ---------------- | --------------------- | ------------------------------------------- |
| **FastAPI**      | REST API framework    | <https://fastapi.tiangolo.com>              |
| **Pydantic v2**  | Schema validation     | <https://docs.pydantic.dev/latest/>         |
| **YOLOv8n**      | Person detection      | <https://docs.ultralytics.com>              |
| **ByteTrack**    | Multi-object tracking | <https://github.com/ifzhang/ByteTrack>      |
| **SQLite**       | Embedded database     | <https://www.sqlite.org/index.html>         |
| **Uvicorn**      | ASGI server           | <https://www.uvicorn.org>                   |
| **pandas**       | POS CSV processing    | <https://pandas.pydata.org>                 |
| **OpenCV**       | Video frame reading   | <https://opencv.org>                        |
| **Chart.js**     | Dashboard bar charts  | <https://www.chartjs.org>                   |
| **DM Sans font** | Dashboard typography  | <https://fonts.google.com/specimen/DM+Sans> |
| **pytest**       | Testing framework     | <https://docs.pytest.org>                   |
| **Docker**       | Containerisation      | <https://www.docker.com>                    |

### Built-in Documentation

Once the server is running:

- **Swagger UI (interactive)**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>
- **Live dashboard**: <http://localhost:8000/>
- **MJPEG stream**: <http://localhost:8000/stream/CAM_01>

### Useful Background Reading

- **Ray-casting point-in-polygon** (how zone assignment works): <https://en.wikipedia.org/wiki/Point_in_polygon>
- **ByteTrack paper**: <https://arxiv.org/abs/2110.06864>
- **YOLOv8 models**: <https://docs.ultralytics.com/models/yolov8/>
- **Server-Sent Events spec**: <https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events>
- **SQLite WAL mode**: <https://www.sqlite.org/wal.html>

### DB Browser (look inside the database)

Download **DB Browser for SQLite** from <https://sqlitebrowser.org>. Open `data/store_intelligence.db`, click the "Browse Data" tab, select the `events` table. You'll see every event stored with timestamp, visitor_id, zone, confidence.

The `daily_stats` table holds the 7-day baseline used by the CONVERSION_DROP anomaly.

---

## Quick Reference Card

```
🚀 START SERVER (local):
   $env:DB_PATH="data/store_intelligence.db"
   $env:CONFIG_DIR="config"
   $env:POS_CSV_PATH="data/pos_transactions.csv"
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

🐳 START SERVER (Docker):
   docker compose up -d

🎥 PROCESS CCTV VIDEOS:
   python scripts/run_pipeline.py --api http://127.0.0.1:8000 --skip-frames 8

🧪 RUN TESTS:
   python -m pytest tests/ -v
   python -m pytest tests/ --cov=app --cov=pipeline

📊 CHECK RESULTS (the footage is from 2026-04-10):
   curl "http://127.0.0.1:8000/stores/ST1008/metrics?date=2026-04-10"
   curl "http://127.0.0.1:8000/stores/ST1008/funnel?date=2026-04-10"
   curl "http://127.0.0.1:8000/stores/ST1008/heatmap?date=2026-04-10"
   curl "http://127.0.0.1:8000/stores/ST1008/anomalies?date=2026-04-10"

🌐 DASHBOARD:
   http://localhost:8000/                ← Live Operations + Store Report
   http://localhost:8000/dashboard/      ← Same dashboard, spec'd URL
   http://localhost:8000/docs            ← Interactive API explorer

🔍 PROBE VIDEOS:
   python scripts/probe_videos.py
   python scripts/save_frames.py         ← saves data/cctv/frames/*.jpg

🐛 FRESH START:
   Remove-Item data\store_intelligence.db   (Windows)
   rm data/store_intelligence.db            (Mac/Linux)

🔥 THE BIG ASSERTION (24 baskets from 101 line items):
   python -m pytest tests/test_pos_edges.py::TestEC35MultiItemBasket -v
```

---

_This guide is the single source of truth for running, understanding, and debugging this system. If something here is wrong or unclear, fix it here — don't leave knowledge in a Slack message._
