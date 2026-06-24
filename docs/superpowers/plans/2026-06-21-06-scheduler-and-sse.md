# Scheduler + SSE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Periodically trigger ingestion (via `apscheduler`) and broadcast progress/status updates to connected clients via Server-Sent Events (SSE).

**Tech Stack:** APScheduler (async scheduler), FastAPI SSE (`sse-starlette`), asyncio.Queue per client.

## Global constraints

- Python 3.14; execution via **uv**. SQLAlchemy 2.0 async. Migrations only via Alembic.
- TDD; `uv run ruff check .` must pass.
- `sse-starlette` for SSE.

---

### Task 1: `SchedulerService` — APScheduler integration

**Files:**
- Create: `src/realestate/scheduler/__init__.py`
- Create: `src/realestate/scheduler/service.py`
- Test: `tests/scheduler/test_service.py`

**Interface:**
```python
class SchedulerService:
    def __init__(self, ingest_fn: Callable[[SearchCriteria], Awaitable[list[ScrapeRun]]], default_criteria: SearchCriteria):
        self.scheduler = AsyncIOScheduler()
        self.ingest_fn = ingest_fn
        self.default_criteria = default_criteria

    async def start(self):
        self.scheduler.add_job(self._run_ingest, "cron", hour="*/6", id="ingest_every_6h")
        self.scheduler.start()

    async def _run_ingest(self):
        try:
            self._report("scheduled_ingest_start", {})
            runs = await self.ingest_fn(self.default_criteria, max_pages=5)
            self._report("scheduled_ingest_done", {"runs": [r.status for r in runs]})
        except Exception as e:
            self._report("scheduled_ingest_error", {"error": str(e)})

    async def stop(self):
        self.scheduler.shutdown()

    def subscribe(self) -> asyncio.Queue:
        # Return a queue for SSE events
        ...

    def _report(self, event: str, data: dict):
        # Push to all subscriber queues
        ...
```

- [ ] **Implement + test (mock `ingest_fn`, verify job is scheduled, verify events pushed to queues).**

---

### Task 2: SSE endpoint

**Files:**
- Create: `src/realestate/api/routes/events.py`
- Modify: `src/realestate/api/app.py` (register router, instantiate `SchedulerService` on startup)
- Test: `tests/api/test_sse.py`

**Endpoint:**
```
GET /api/v1/events
Accept: text/event-stream
→ SSE stream with events: ingest_start, ingest_done, ingest_error, heartbeat (every 30s)
```

**Test (httpx with `stream=True`):**
- Connect to SSE endpoint.
- Trigger manual ingest via test-only helper or mock.
- Verify events received within timeout.
- Connection closes after `max_duration` or on client disconnect.

---

### Task 3: `POST /api/v1/ingest` — manual trigger

**Files:**
- Create: `src/realestate/api/routes/ingest.py`
- Modify: `src/realestate/api/app.py`
- Test: `tests/api/test_ingest_endpoint.py`

**Endpoint:**
```
POST /api/v1/ingest
Body: {"source_ids": ["otodom"] | null, "max_pages": 5}
Response: {"run_ids": [1, 2, 3]}
```

- Calls `IngestionService.ingest()` (from Plan 3) in background task (`BackgroundTasks` or `asyncio.create_task`).
- Returns immediately with `run_ids`.
- Pushes SSE events via `SchedulerService._report`.

---

### Task 4: Startup/shutdown lifecycle

**Modify `app.py`:**
- On startup: init `SchedulerService`, call `start()`, attach to `app.state`.
- On shutdown: call `stop()`.
- Pass `IngestionService` and `enrichment_client` through app state / dependency injection.

---

### Task 5: `POST /api/v1/enrich` — manual enrichment trigger

**Files:**
- Create: `src/realestate/api/routes/enrich.py`
- Modify: `src/realestate/api/app.py`
- Test: `tests/api/test_enrich_endpoint.py`

**Endpoint:**
```
POST /api/v1/enrich
Body: {"limit": 50}
Response: {"processed": 42, "errors": 0}
```

Called manually or by scheduler (optional, separate cron job in scheduler).

---

## Definition of done (Plan 6)
- APScheduler runs ingestion every 6 hours.
- `POST /api/v1/ingest` triggers manual ingestion.
- `GET /api/v1/events` streams SSE events (ingest start/done/error, heartbeat).
- `POST /api/v1/enrich` triggers manual enrichment.
- Clean startup/shutdown lifecycle.
- Tests cover scheduler, SSE stream, manual triggers.
