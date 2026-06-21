# Scheduler + SSE (postęp scrapingu na żywo) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać (1) okresowy inkrementalny scraping przez APScheduler (interwał z konfiguracji/`app_settings`, ta sama logika co ręczny trigger) oraz (2) strumień zdarzeń `GET /events` (SSE) z postępem scrapingu na żywo, zasilany wewnętrznym, in-process autobusem zdarzeń.

**Architecture:** Lekki, in-process `EventBus` (asyncio kolejki per subskrybent) rozsyła zdarzenia postępu. `IngestionService.ingest` zyskuje opcjonalny async hook `on_run`, wołany po każdym zakończonym `ScrapeRun`; endpoint `POST /scrape` przekazuje hook publikujący zdarzenia do autobusu. `GET /events` subskrybuje autobus i streamuje zdarzenia w formacie SSE. `ScrapeScheduler` (APScheduler `AsyncIOScheduler`) okresowo uruchamia zadanie, które dla każdego zapisanego wyszukiwania (z miastem) wykonuje tę samą `IngestionService.ingest`. Autobus i scheduler żyją na `app.state`, budowane w `lifespan`.

**Tech Stack:** Python 3.14, FastAPI (StreamingResponse/SSE), APScheduler (AsyncIOScheduler), asyncio, SQLAlchemy 2.0 async, httpx (ASGITransport w testach).

## Global Constraints

- Stack: Python 3.14, SQLAlchemy 2.0 async + asyncpg, PostgreSQL 18 + pgvector, FastAPI, APScheduler. Uruchamianie: `uv run`.
- TDD: test → implementacja → commit. Testy DB/API na realnym kontenerze pg18 (`engine` fixture). Testy API: `httpx.ASGITransport` + `AsyncClient` + `app.dependency_overrides`.
- Lint `uv run ruff check .` musi przechodzić (E,F,I,UP,B; line-length 100; `# noqa: B008` dozwolone na domyślnych `Depends()`/`Query()` w FastAPI).
- **Determinizm testów:** NIE testujemy zegara APScheduler (nie polegamy na realnym odpaleniu po czasie). Testujemy: korutynę zadania bezpośrednio oraz że `start()` rejestruje zadanie z poprawnym interwałem (`scheduler.get_jobs()`).
- Zmiany w `IngestionService.ingest` muszą być WSTECZNIE KOMPATYBILNE: nowy parametr `on_run` jest opcjonalny (`None` domyślnie); istniejące wywołania i testy działają bez zmian.
- Brak nowych zmian schematu (żadnej migracji w tym planie).
- Degradacja: brak zapisanych wyszukiwań / brak miasta w filtrach → zadanie schedulera jest no-op (nie rzuca).
- Pyright/import-resolution błędy to znane false-positives (src-layout) — brama jakości to `ruff` + `pytest`.

---

### Task 1: `EventBus` — in-process async pub/sub

**Files:**
- Create: `src/realestate/events/__init__.py` (pusty)
- Create: `src/realestate/events/bus.py`
- Test: `tests/events/__init__.py` (pusty), `tests/events/test_event_bus.py`

**Interfaces:**
- Produces:
  - `class EventBus`:
    - `__init__(self, *, max_queue: int = 100)`.
    - `subscribe(self) -> AbstractAsyncContextManager[asyncio.Queue[dict]]`: async context manager; przy wejściu rejestruje nową `asyncio.Queue(maxsize=max_queue)` i ją zwraca; przy wyjściu wyrejestrowuje.
    - `publish(self, event: dict) -> None`: dla każdej zarejestrowanej kolejki `put_nowait(event)`; jeśli kolejka pełna (`asyncio.QueueFull`) — pomiń tę kolejkę (drop, bez wyjątku).
    - `subscriber_count` (property) -> int.

- [ ] **Step 1: Write the failing test**

```python
# tests/events/test_event_bus.py
import asyncio

import pytest

from realestate.events.bus import EventBus


async def test_subscribe_receives_published_event():
    bus = EventBus()
    async with bus.subscribe() as queue:
        assert bus.subscriber_count == 1
        bus.publish({"type": "scrape", "source_id": "otodom"})
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event == {"type": "scrape", "source_id": "otodom"}
    assert bus.subscriber_count == 0  # wyrejestrowano po wyjściu


async def test_multiple_subscribers_all_receive():
    bus = EventBus()
    async with bus.subscribe() as q1, bus.subscribe() as q2:
        bus.publish({"n": 1})
        assert (await asyncio.wait_for(q1.get(), 1)) == {"n": 1}
        assert (await asyncio.wait_for(q2.get(), 1)) == {"n": 1}


async def test_publish_with_no_subscribers_is_noop():
    bus = EventBus()
    bus.publish({"n": 1})  # nie rzuca
    assert bus.subscriber_count == 0


async def test_full_queue_drops_without_error():
    bus = EventBus(max_queue=1)
    async with bus.subscribe() as queue:
        bus.publish({"n": 1})
        bus.publish({"n": 2})  # kolejka pełna -> drop, brak wyjątku
        assert (await asyncio.wait_for(queue.get(), 1)) == {"n": 1}
        assert queue.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/events/test_event_bus.py -v`
Expected: FAIL — brak modułu `realestate.events`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/events/bus.py
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager


class EventBus:
    """In-process pub/sub po asyncio.Queue. Jeden proces, brak trwałości."""

    def __init__(self, *, max_queue: int = 100) -> None:
        self._max_queue = max_queue
        self._subscribers: set[asyncio.Queue] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @asynccontextmanager
    async def subscribe(self):
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def publish(self, event: dict) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/events/test_event_bus.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/events tests/events
git commit -m "feat: EventBus — in-process async pub/sub"
```

---

### Task 2: Hook postępu `on_run` w `IngestionService.ingest`

**Files:**
- Modify: `src/realestate/ingestion/service.py`
- Test: `tests/ingestion/test_ingest_on_run_hook.py`

**Interfaces:**
- Consumes: istniejący `IngestionService`.
- Produces (rozszerzenie sygnatury — wstecznie kompatybilne):
  - `async def ingest(self, criteria, *, source_ids=None, max_pages=1, on_run: Callable[[ScrapeRun], Awaitable[None]] | None = None) -> list[ScrapeRun]`.
  - Po dołączeniu każdego `run` do `runs` (po commit) i przed kolejnym źródłem: jeśli `on_run is not None` → `await on_run(run)`. Hook NIE może wywrócić ingestii: owiń w `try/except Exception: pass` (postęp jest best-effort).

- [ ] **Step 1: Write the failing test**

```python
# tests/ingestion/test_ingest_on_run_hook.py
import pytest

from realestate.db.engine import create_session_factory
from realestate.ingestion.service import IngestionService
from realestate.models import Base
from realestate.scrapers.base import SearchCriteria
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    def __init__(self):
        self.first = True
    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        return '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}</script></html>'


@pytest.fixture(autouse=True)
def _only_otodom():
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401
    saved = dict(base._REGISTRY)
    base._REGISTRY.clear()
    base._REGISTRY.update({"otodom": saved["otodom"]})
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def test_on_run_called_per_source(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _OneSourceFetcher())

    seen = []

    async def on_run(run):
        seen.append((run.source_id, run.status.value, run.new_count))

    runs = await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"],
                            max_pages=2, on_run=on_run)
    assert len(runs) == 1
    assert len(seen) == 1
    assert seen[0][0] == "otodom"
    assert seen[0][1] == "success"


async def test_on_run_exception_does_not_break_ingest(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    svc = IngestionService(factory, _OneSourceFetcher())

    async def boom(run):
        raise RuntimeError("hook failed")

    runs = await svc.ingest(SearchCriteria(city="gdansk"), source_ids=["otodom"],
                            max_pages=2, on_run=boom)
    assert len(runs) == 1  # ingestia ukończona mimo wyjątku w hooku
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/ingestion/test_ingest_on_run_hook.py -v`
Expected: FAIL — `ingest()` nie przyjmuje `on_run`.

- [ ] **Step 3: Write minimal implementation**

W `src/realestate/ingestion/service.py`:
- dodaj importy: `from collections.abc import Awaitable, Callable`.
- zmień sygnaturę `ingest` dodając `on_run: Callable[[ScrapeRun], Awaitable[None]] | None = None` (na końcu, po `max_pages`).
- po `runs.append(run)` dodaj:
```python
            if on_run is not None:
                try:
                    await on_run(run)
                except Exception:
                    pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/ingestion/test_ingest_on_run_hook.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/ingestion/service.py tests/ingestion/test_ingest_on_run_hook.py
git commit -m "feat: opcjonalny hook on_run w IngestionService.ingest (postęp)"
```

---

### Task 3: Endpoint SSE `GET /events`

**Files:**
- Create: `src/realestate/api/routes_events.py`
- Modify: `src/realestate/api/deps.py` (zależność autobusu), `src/realestate/api/app.py` (autobus w lifespan + include router)
- Test: `tests/api/test_events_api.py`

**Interfaces:**
- Consumes: `EventBus`.
- Produces:
  - `deps.py`: `get_event_bus_dep(request) -> EventBus` (czyta `request.app.state.event_bus`).
  - `routes_events.py`:
    - `def format_sse(event: dict) -> str`: zwraca `f"event: {event.get('type','message')}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"`.
    - `async def event_stream(bus: EventBus, *, limit: int | None = None) -> AsyncIterator[str]`: `async with bus.subscribe() as queue:` pętla — `event = await queue.get()`, `yield format_sse(event)`, licznik; przerwij gdy `limit is not None and count >= limit`.
    - `GET /events?limit=` → `StreamingResponse(event_stream(bus, limit=limit), media_type="text/event-stream")`. `limit` domyślnie `None` (strumień nieskończony dla realnych klientów); skończony w testach.
  - `app.py`: w `lifespan` (startup) ustaw `app.state.event_bus = EventBus()` (przed `yield`); dołącz `routes_events.router`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_events_api.py
import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import get_event_bus_dep
from realestate.api.routes_events import format_sse
from realestate.events.bus import EventBus


def test_format_sse_shape():
    out = format_sse({"type": "scrape", "source_id": "otodom"})
    assert out.startswith("event: scrape\n")
    assert '"source_id": "otodom"' in out
    assert out.endswith("\n\n")


async def test_events_stream_emits_published(engine):
    app = create_app()
    bus = EventBus()
    app.dependency_overrides[get_event_bus_dep] = lambda: bus

    async def _publish_later():
        await asyncio.sleep(0.05)
        bus.publish({"type": "scrape", "source_id": "otodom"})
        bus.publish({"type": "scrape", "source_id": "nieruchomosci-online"})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        task = asyncio.create_task(_publish_later())
        async with client.stream("GET", "/events", params={"limit": 2}) as resp:
            assert resp.status_code == 200
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
        await task

    assert "otodom" in body
    assert "nieruchomosci-online" in body
    assert body.count("event: scrape") == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_events_api.py -v`
Expected: FAIL — brak `routes_events`/zależności.

- [ ] **Step 3: Write minimal implementation**

```python
# src/realestate/api/routes_events.py
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from realestate.api.deps import get_event_bus_dep
from realestate.events.bus import EventBus

router = APIRouter()


def format_sse(event: dict) -> str:
    etype = event.get("type", "message")
    return f"event: {etype}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


async def event_stream(bus: EventBus, *, limit: int | None = None) -> AsyncIterator[str]:
    async with bus.subscribe() as queue:
        count = 0
        while limit is None or count < limit:
            event = await queue.get()
            yield format_sse(event)
            count += 1


@router.get("/events")
async def events(
    limit: int | None = None,
    bus: EventBus = Depends(get_event_bus_dep),  # noqa: B008
) -> StreamingResponse:
    return StreamingResponse(event_stream(bus, limit=limit), media_type="text/event-stream")
```

W `deps.py` dodaj:
```python
def get_event_bus_dep(request: Request):
    return request.app.state.event_bus
```

W `app.py` w `lifespan` startup dodaj `app.state.event_bus = EventBus()` (import `from realestate.events.bus import EventBus`), oraz `app.include_router(events_router)` (import routera). **WAŻNE:** autobus tworzymy w `lifespan`, ale testy nadpisują `get_event_bus_dep`, więc brak uruchomienia lifespan pod ASGITransport nie przeszkadza.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_events_api.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Commit**

```bash
git add src/realestate/api/routes_events.py src/realestate/api/deps.py src/realestate/api/app.py tests/api/test_events_api.py
git commit -m "feat: SSE GET /events + autobus zdarzeń w lifespan"
```

---

### Task 4: `POST /scrape` publikuje postęp do autobusu

**Files:**
- Modify: `src/realestate/api/routes_scrape.py`
- Test: `tests/api/test_scrape_events.py`

**Interfaces:**
- Consumes: `EventBus` (przez `get_event_bus_dep`), `IngestionService.ingest(..., on_run=...)`.
- Produces (zmiana w `POST /scrape`):
  - dodaj zależność `bus: EventBus = Depends(get_event_bus_dep)`.
  - zbuduj async hook `on_run(run)` publikujący do autobusu zdarzenie:
    `{"type": "scrape", "source_id": run.source_id, "status": run.status.value, "new": run.new_count, "updated": run.updated_count, "gone": run.gone_count, "unchanged": run.unchanged_count}`.
  - przekaż `on_run=on_run` do `service.ingest(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_scrape_events.py
import pytest
from httpx import ASGITransport, AsyncClient

from realestate.api.app import create_app
from realestate.api.deps import get_event_bus_dep, get_fetcher_dep, get_session_factory
from realestate.db.engine import create_session_factory
from realestate.events.bus import EventBus
from realestate.models import Base
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    def __init__(self):
        self.first = True
    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        return '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}</script></html>'


@pytest.fixture(autouse=True)
def _only_otodom():
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401
    saved = dict(base._REGISTRY)
    base._REGISTRY.clear()
    base._REGISTRY.update({"otodom": saved["otodom"]})
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def test_scrape_publishes_events(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app = create_app()
    factory = create_session_factory(engine)
    bus = EventBus()
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_fetcher_dep] = lambda: _OneSourceFetcher()
    app.dependency_overrides[get_event_bus_dep] = lambda: bus

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        async with bus.subscribe() as queue:
            resp = await client.post("/scrape", json={"city": "gdansk",
                                                       "source_ids": ["otodom"], "max_pages": 2})
            assert resp.status_code == 200
            event = queue.get_nowait()
    assert event["type"] == "scrape"
    assert event["source_id"] == "otodom"
    assert event["status"] == "success"
    assert event["new"] >= 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/api/test_scrape_events.py -v`
Expected: FAIL — brak publikacji (KeyError/queue empty).

- [ ] **Step 3: Write minimal implementation**

W `src/realestate/api/routes_scrape.py`, zmodyfikuj `trigger_scrape`:
```python
from realestate.api.deps import get_event_bus_dep  # dołącz do importów
from realestate.events.bus import EventBus


@router.post("/scrape", response_model=ScrapeResponse)
async def trigger_scrape(
    body: ScrapeRequest,
    session_factory=Depends(get_session_factory),  # noqa: B008
    fetcher=Depends(get_fetcher_dep),  # noqa: B008
    bus: EventBus = Depends(get_event_bus_dep),  # noqa: B008
) -> ScrapeResponse:
    criteria = SearchCriteria(
        city=body.city, min_price=body.min_price, max_price=body.max_price,
        min_area=body.min_area, max_area=body.max_area, min_rooms=body.min_rooms,
        max_rooms=body.max_rooms, market=body.market,
    )

    async def on_run(run) -> None:
        bus.publish({
            "type": "scrape", "source_id": run.source_id, "status": run.status.value,
            "new": run.new_count, "updated": run.updated_count,
            "gone": run.gone_count, "unchanged": run.unchanged_count,
        })

    service = IngestionService(session_factory, fetcher)
    runs = await service.ingest(criteria, source_ids=body.source_ids,
                                max_pages=body.max_pages, on_run=on_run)
    return ScrapeResponse(runs=[ScrapeRunOut.from_run(r) for r in runs])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/api/test_scrape_events.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/realestate/api/routes_scrape.py tests/api/test_scrape_events.py
git commit -m "feat: POST /scrape publikuje postęp do autobusu zdarzeń"
```

---

### Task 5: Scheduler (APScheduler) — okresowy inkrementalny scrape

**Files:**
- Modify: `pyproject.toml` (dodaj `apscheduler>=3.10,<4` do `dependencies`)
- Modify: `src/realestate/config.py` (ustawienia schedulera)
- Create: `src/realestate/scheduler/__init__.py` (pusty)
- Create: `src/realestate/scheduler/job.py`
- Create: `src/realestate/scheduler/runner.py`
- Test: `tests/scheduler/__init__.py` (pusty), `tests/scheduler/test_scheduler_job.py`, `tests/scheduler/test_scheduler_runner.py`

**Interfaces:**
- Consumes: `IngestionService`, `SavedSearchRepository`, `SearchCriteria`, `EventBus`, `async_sessionmaker`, `AsyncIOScheduler`.
- Produces:
  - W `Settings`: `scheduler_enabled: bool = False`, `scheduler_default_interval_minutes: int = 360`.
  - `job.py`: `async def run_scheduled_scrape(session_factory, fetcher, bus, *, max_pages: int = 1) -> int`:
    - W nowej sesji wczytaj `SavedSearchRepository.list_all()`.
    - Dla każdego zapisanego wyszukiwania, jeśli `filters` zawiera prawdziwe `city` (str) → zbuduj `SearchCriteria(city=..., min_price=..., max_price=..., min_area=..., max_area=..., min_rooms=..., max_rooms=..., market=...)` z dostępnych kluczy `filters` (brakujące → None) i uruchom `IngestionService(session_factory, fetcher).ingest(criteria, max_pages=max_pages, on_run=<publikacja do bus>)`.
    - Zwróć liczbę przetworzonych wyszukiwań (z miastem). Wyszukiwania bez `city` pomiń. Brak wyszukiwań → zwróć 0 (no-op).
  - `runner.py`: `class ScrapeScheduler`:
    - `__init__(self, session_factory, fetcher, bus, *, scheduler: AsyncIOScheduler | None = None)` (domyślnie tworzy własny `AsyncIOScheduler`).
    - `start(self, *, interval_minutes: int) -> None`: `add_job(self._job, "interval", minutes=interval_minutes, id="scrape", replace_existing=True)` i `self._scheduler.start()` (jeśli nie działa).
    - `reschedule(self, *, interval_minutes: int) -> None`: `self._scheduler.reschedule_job("scrape", trigger="interval", minutes=interval_minutes)`.
    - `shutdown(self) -> None`: `self._scheduler.shutdown(wait=False)` (jeśli działa).
    - `async def _job(self) -> None`: woła `run_scheduled_scrape(self.session_factory, self.fetcher, self.bus)`.
    - właściwość/dostęp do `self._scheduler` (lub metoda `jobs()` zwracająca `self._scheduler.get_jobs()`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/scheduler/test_scheduler_job.py
from datetime import UTC, datetime

import pytest

from realestate.db.engine import create_session_factory
from realestate.events.bus import EventBus
from realestate.models import Base
from realestate.models.user_data import SavedSearch
from realestate.scheduler.job import run_scheduled_scrape
from sqlalchemy.ext.asyncio import AsyncSession
from tests.fixtures.loader import load_fixture


class _OneSourceFetcher:
    def __init__(self):
        self.first = True
    async def fetch(self, url: str) -> str:
        if self.first:
            self.first = False
            return load_fixture("otodom_search_gdansk")
        return '<html><script id="__NEXT_DATA__" type="application/json">{"props":{"pageProps":{"data":{"searchAds":{"items":[]}}}}}</script></html>'


@pytest.fixture(autouse=True)
def _only_otodom():
    import realestate.scrapers.base as base
    import realestate.scrapers.otodom  # noqa: F401
    saved = dict(base._REGISTRY)
    base._REGISTRY.clear()
    base._REGISTRY.update({"otodom": saved["otodom"]})
    yield
    base._REGISTRY.clear()
    base._REGISTRY.update(saved)


async def test_job_runs_ingest_for_saved_search_with_city(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with AsyncSession(engine, expire_on_commit=False) as s:
        s.add(SavedSearch(name="gda", filters={"city": "gdansk", "max_pages": 2},
                          nl_query=None, created_at=datetime.now(UTC)))
        s.add(SavedSearch(name="bez miasta", filters={"max_price": 500000},
                          nl_query=None, created_at=datetime.now(UTC)))
        await s.commit()

    bus = EventBus()
    processed = await run_scheduled_scrape(factory, _OneSourceFetcher(), bus, max_pages=2)
    assert processed == 1  # tylko wyszukiwanie z miastem

    # zweryfikuj, że powstały oferty
    from realestate.repositories.listings import ListingRepository
    async with AsyncSession(engine, expire_on_commit=False) as s:
        assert await ListingRepository(s).count_active() >= 20


async def test_job_noop_without_saved_searches(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    bus = EventBus()
    assert await run_scheduled_scrape(factory, _OneSourceFetcher(), bus) == 0
```

```python
# tests/scheduler/test_scheduler_runner.py
import pytest

from realestate.events.bus import EventBus
from realestate.scheduler.runner import ScrapeScheduler


async def test_start_registers_job_with_interval():
    sched = ScrapeScheduler(session_factory=None, fetcher=None, bus=EventBus())
    try:
        sched.start(interval_minutes=15)
        jobs = sched.jobs()
        assert len(jobs) == 1
        assert jobs[0].id == "scrape"
    finally:
        sched.shutdown()


async def test_reschedule_changes_interval():
    sched = ScrapeScheduler(session_factory=None, fetcher=None, bus=EventBus())
    try:
        sched.start(interval_minutes=15)
        sched.reschedule(interval_minutes=60)
        assert len(sched.jobs()) == 1  # nadal jedno zadanie
    finally:
        sched.shutdown()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/scheduler/ -v`
Expected: FAIL — brak modułów/zależności (apscheduler).

- [ ] **Step 3: Write minimal implementation**

Dodaj `apscheduler>=3.10,<4` do `[project] dependencies` w `pyproject.toml` (uruchom `uv sync` jeśli trzeba).

W `src/realestate/config.py` dodaj do `Settings` (po polach LLM):
```python
    scheduler_enabled: bool = False
    scheduler_default_interval_minutes: int = 360
```

```python
# src/realestate/scheduler/job.py
from __future__ import annotations

from realestate.events.bus import EventBus
from realestate.ingestion.service import IngestionService
from realestate.repositories.user_data import SavedSearchRepository
from realestate.scrapers.base import SearchCriteria


def _criteria_from_filters(filters: dict) -> SearchCriteria | None:
    city = filters.get("city")
    if not isinstance(city, str) or not city:
        return None
    return SearchCriteria(
        city=city,
        min_price=filters.get("min_price"),
        max_price=filters.get("max_price"),
        min_area=filters.get("min_area"),
        max_area=filters.get("max_area"),
        min_rooms=filters.get("min_rooms"),
        max_rooms=filters.get("max_rooms"),
        market=filters.get("market"),
    )


async def run_scheduled_scrape(session_factory, fetcher, bus: EventBus, *, max_pages: int = 1) -> int:
    async with session_factory() as session:
        searches = await SavedSearchRepository(session).list_all()

    async def on_run(run) -> None:
        bus.publish({
            "type": "scrape", "source_id": run.source_id, "status": run.status.value,
            "new": run.new_count, "updated": run.updated_count,
            "gone": run.gone_count, "unchanged": run.unchanged_count,
        })

    service = IngestionService(session_factory, fetcher)
    processed = 0
    for search in searches:
        criteria = _criteria_from_filters(search.filters or {})
        if criteria is None:
            continue
        pages = (search.filters or {}).get("max_pages", max_pages)
        await service.ingest(criteria, max_pages=pages, on_run=on_run)
        processed += 1
    return processed
```

```python
# src/realestate/scheduler/runner.py
from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from realestate.events.bus import EventBus
from realestate.scheduler.job import run_scheduled_scrape


class ScrapeScheduler:
    def __init__(self, session_factory, fetcher, bus: EventBus, *,
                 scheduler: AsyncIOScheduler | None = None) -> None:
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.bus = bus
        self._scheduler = scheduler or AsyncIOScheduler()

    async def _job(self) -> None:
        await run_scheduled_scrape(self.session_factory, self.fetcher, self.bus)

    def start(self, *, interval_minutes: int) -> None:
        self._scheduler.add_job(self._job, "interval", minutes=interval_minutes,
                                id="scrape", replace_existing=True)
        if not self._scheduler.running:
            self._scheduler.start()

    def reschedule(self, *, interval_minutes: int) -> None:
        self._scheduler.reschedule_job("scrape", trigger="interval", minutes=interval_minutes)

    def jobs(self):
        return self._scheduler.get_jobs()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/scheduler/ -v`
Expected: PASS (3 testy).

- [ ] **Step 5: Pełny zestaw + lint**

Run: `uv run pytest && uv run ruff check .`
Expected: wszystko zielone, ruff czysty.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/realestate/config.py src/realestate/scheduler tests/scheduler
git commit -m "feat: ScrapeScheduler (APScheduler) + zadanie okresowego scrapingu zapisanych wyszukiwań"
```

---

## Definicja ukończenia (Plan 6)
- `uv run pytest` zielony; `uv run ruff check .` bez błędów.
- `EventBus`: in-process pub/sub (asyncio), bezpieczny przy pełnej kolejce i bez subskrybentów.
- `IngestionService.ingest` ma opcjonalny hook `on_run` (wstecznie kompatybilny, best-effort).
- `GET /events` (SSE) streamuje zdarzenia postępu w formacie `event:`/`data:`.
- `POST /scrape` publikuje postęp per-source do autobusu (widoczny w `/events`).
- `ScrapeScheduler` (APScheduler `AsyncIOScheduler`): `start`/`reschedule`/`shutdown`; zadanie uruchamia tę samą `IngestionService.ingest` dla zapisanych wyszukiwań z miastem (no-op bez nich). Testowane bez polegania na zegarze.
