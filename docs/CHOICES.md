# Architectural Choices

This document captures three key architectural decisions made during the development of RetailVisionAI. Each section explains the alternatives considered, the initial AI recommendation, the final choice, and how the decision supports the project's North Star: **accurate retail intelligence that executives can trust.**

---

# Decision 1: YOLOv8n + ByteTrack for Detection and Tracking

## Options Considered

* YOLOv8n + ByteTrack
* YOLOv5 + DeepSORT
* Detectron2 + StrongSORT
* MMDetection + OC-SORT

## Initial AI Recommendation

The initial recommendation favored **DeepSORT**, highlighting its appearance-based matching and strong performance under occlusion. It suggested that DeepSORT would better maintain identities in crowded environments and align with common approaches in retail analytics literature.

## Final Choice

**YOLOv8n + ByteTrack**, with cross-camera re-identification handled separately through a lightweight `ReIDGallery`.

## Rationale

The primary constraint for this project was deployment simplicity. The target acceptance criterion was:

> A reviewer should be able to clone the repository and run the entire system with minimal setup.

ByteTrack is bundled directly within Ultralytics, meaning a single dependency provides both detection and tracking functionality. This significantly reduces installation complexity compared to DeepSORT, which requires additional appearance models and weight management.

Cross-camera re-identification was treated as a separate problem. In a retail environment, customers may leave and return after several minutes. Motion-based tracking is ineffective in such cases regardless of tracker choice. Instead, a dedicated `ReIDGallery` was implemented using appearance embeddings, configurable matching thresholds, and temporal windows.

This separation allows:

* ByteTrack to focus on short-term tracking and occlusion handling.
* ReIDGallery to handle long-term visitor re-identification.

## Connection to the North Star

Reliable tracking preserves visitor identity continuity and prevents track fragmentation. This keeps visitor counts accurate and avoids artificially inflating the denominator used in conversion-rate calculations.

---

# Decision 2: Event Log as Source of Truth with Derived Sessions

## Options Considered

* Pure event-log architecture
* Pre-aggregated session storage
* Hybrid event-log plus materialized sessions

## Initial AI Recommendation

The original recommendation favored a pure event-log design, emphasizing flexibility and the ability to recompute future metrics from historical events.

## Final Choice

A hybrid approach:

* Events remain the permanent source of truth.
* Sessions are generated dynamically through `build_sessions()`.
* A small `daily_stats` table stores cross-day aggregates required for anomaly detection.

## Rationale

While the event log provides flexibility, most business metrics require a visitor-session abstraction.

Examples:

* Multiple ENTRY events may belong to the same visitor.
* Staff members should be excluded from customer metrics.
* Re-entry events should not inflate visitor counts.

Implementing these rules directly against raw events would create duplicated logic across metrics, funnels, heatmaps, and anomaly detection modules.

Instead, session construction is centralized in a single location:

```text
events → build_sessions() → analytics modules
```

This guarantees consistent interpretation of visitor behavior throughout the platform.

The event log remains unchanged on disk, allowing historical reprocessing whenever business rules evolve. During development, session logic changed multiple times, making this flexibility particularly valuable.

The only intentional aggregation is `daily_stats`, which supports long-term trend analysis and anomaly baselines.

## Connection to the North Star

Every dashboard component derives visitor counts from the same session-building logic. This ensures executives receive a consistent answer regardless of which analytics view they inspect.

---

# Decision 3: SQLite Behind a Repository Interface

## Options Considered

* SQLite with direct access
* SQLite behind a repository abstraction
* PostgreSQL from day one
* DuckDB for analytics with SQLite for ingestion

## Initial AI Recommendation

The initial recommendation suggested PostgreSQL, citing scalability, concurrent write support, and common production deployment patterns.

## Final Choice

SQLite behind a narrow repository interface (`SQLiteRepo`).

The interface exposes only the operations required by the application:

* insert_ignore()
* events_for()
* last_event_ts()
* daily_stats helpers

## Rationale

Deployment simplicity was prioritized over premature scalability.

Using PostgreSQL would require:

* An additional container
* Connection configuration
* Database initialization
* Service dependency management
* Migration handling

Each additional component increases deployment complexity and introduces new failure points during evaluation.

SQLite offers several advantages for this project's scale:

* Zero external dependencies
* Automatic database creation
* Simple backups
* Consistent behavior across environments
* Sufficient performance for current event volumes

The repository abstraction preserves future flexibility. A PostgreSQL implementation can replace SQLite without requiring changes to business logic, analytics modules, or test suites.

## Connection to the North Star

Using SQLite ensures that the demonstration environment behaves identically to production logic. The dashboard presented during evaluation is powered by the same event processing, session generation, and analytics pipeline that would operate in a deployed environment.

The result is a system that prioritizes correctness, reproducibility, and ease of adoption while remaining extensible for future growth.
