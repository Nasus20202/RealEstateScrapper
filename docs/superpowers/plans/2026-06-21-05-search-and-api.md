# Search + API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose aggregated listings via a FastAPI REST API with:
1. **Vector search** — cosine distance on `embedding` (raw SQL + pgvector).
2. **Structured filters** — market, price range, area, rooms, floor, status, city, etc.
3. **Sorting** — by price, area, rooms, price_per_m2, or by relevance (vector search only).
4. **Pagination** — cursor-based (`cursor` + `limit`).
5. **OpenAPI/Swagger** — auto-generated from Pydantic models.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0 async, pgvector (raw SQL).

## Global constraints

- Python 3.14; execution via **uv**. SQLAlchemy 2.0 async. Migrations only via Alembic.
- TDD; `uv run ruff check .` must pass.
- API prefix: `/api/v1`.
- Cursor = base64-encoded JSON of `{id, sort_value}` for the last item. Deterministic ordering via `(sort_field, id)` tiebreaker.
- Vector search returns only listings with non-null `embedding`.
- All endpoints return `ListingsResponse` model with `items: list[ListingResponse]` and `next_cursor: str | None`.

---

### Task 1: Pydantic schemas

**Files:**
- Create: `src/realestate/api/schemas/__init__.py`
- Create: `src/realestate/api/schemas/listing.py`
- Create: `src/realestate/api/schemas/search.py`

**Interfaces:**

`listing.py`:
```python
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

class ListingResponse(BaseModel):
    id: int
    external_id: str
    source_id: str
    title: str
    description: str | None
    enriched_description: str | None
    price: Decimal | None
    price_per_m2: Decimal | None
    area_m2: float | None
    rooms: int | None
    floor: int | None
    total_floors: int | None
    market: str | None
    status: str
    city: str | None
    district: str | None
    street: str | None
    lat: float | None
    lon: float | None
    images: list[str]
    url: str
    posted_at: datetime | None
    first_seen: datetime
    last_seen: datetime
    similarity: float | None = Field(None, description="Cosine similarity if vector search")

class ListingsResponse(BaseModel):
    items: list[ListingResponse]
    next_cursor: str | None
```

`search.py`:
```python
from decimal import Decimal
from pydantic import BaseModel, Field

class SearchFilters(BaseModel):
    query: str | None = None  # full-text search on title/description
    city: str | None = None
    district: str | None = None
    market: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    area_min: float | None = None
    area_max: float | None = None
    rooms_min: int | None = None
    rooms_max: int | None = None
    status: str = "active"

class SearchRequest(BaseModel):
    filters: SearchFilters = Field(default_factory=SearchFilters)
    sort: str = "price"  # price, area, rooms, price_per_m2, created_at, relevance
    sort_dir: str = "asc"  # asc, desc
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = None
```

- [ ] **Implement schemas** — commit after.

---

### Task 2: Query builder (structured filters + sorting + cursor)

**Files:**
- Create: `src/realestate/api/search/__init__.py`
- Create: `src/realestate/api/search/builder.py`
- Test: `tests/api/test_search_builder.py`

**Interface:**
```python
@dataclass
class SearchQuery:
    sql: str
    params: dict
    sort_field: str
    sort_dir: str

class SearchQueryBuilder:
    def build(self, req: SearchRequest) -> SearchQuery
```

Generates SQL of the form:
```sql
SELECT id, ... (all ListingResponse columns), 1.0 AS similarity
FROM listings
WHERE status = :status
  AND (:city IS NULL OR city = :city)
  AND (:district IS NULL OR district = :district)
  AND (:market IS NULL OR market = :market)
  AND (:price_min IS NULL OR price >= :price_min)
  AND (:price_max IS NULL OR price <= :price_max)
  AND (:area_min IS NULL OR area_m2 >= :area_min)
  AND (:area_max IS NULL OR area_m2 <= :area_max)
  AND (:rooms_min IS NULL OR rooms >= :rooms_min)
  AND (:rooms_max IS NULL OR rooms <= :rooms_max)
ORDER BY <sort_field> <sort_dir>, id <sort_dir>
LIMIT :limit + 1  -- fetch extra row for cursor
OFFSET :offset  -- or use cursor WHERE clause
```

For cursor-based pagination with `cursor`:
- Decode `next_cursor` to `{id, sort_value}`.
- Add `WHERE (sort_field > :sort_value) OR (sort_field = :sort_value AND id > :id)`.
- No `OFFSET`.

Vector search variant (when `query` is provided):
```sql
SELECT id, ..., 1 - (embedding <=> :query_embedding) AS similarity
FROM listings
WHERE embedding IS NOT NULL AND status = :status
  AND ...
ORDER BY embedding <=> :query_embedding, id
LIMIT :limit + 1
```
Where `:query_embedding` is a pgvector-compatible string `[...]`.

- [ ] **Tests** — `test_build_filter_query`, `test_build_with_cursor`, `test_build_vector_search`, `test_invalid_sort_field_raises`.

- [ ] **Implement** — commit.

---

### Task 3: `SearchService` (vector embedding + search logic)

**Files:**
- Create: `src/realestate/api/search/service.py`
- Test: `tests/api/test_search_service.py`

**Interface:**
```python
class SearchService:
    def __init__(self, session_factory: async_sessionmaker, enrichment_client: EnrichmentClient | None = None):
        ...

    async def search(self, req: SearchRequest) -> ListingsResponse:
        if req.filters.query:
            return await self._vector_search(req)
        return await self._structured_search(req)

    async def _vector_search(self, req: SearchRequest) -> ListingsResponse:
        embedding = await self.client.generate_embedding(req.filters.query)
        # Use SearchQueryBuilder with vector SQL
        ...

    async def _structured_search(self, req: SearchRequest) -> ListingsResponse:
        # Use SearchQueryBuilder with structured SQL
        ...
```

**Tests:** mock `enrichment_client.generate_embedding` to return fixed vector. Test structured vs vector search, cursor pagination, empty results. Use real DB with seed listings.

- [ ] **Implement + test + commit.**

---

### Task 4: FastAPI endpoints

**Files:**
- Create: `src/realestate/api/routes/search.py`
- Modify: `src/realestate/api/app.py` (mount router)
- Test: `tests/api/test_search_endpoints.py`

**Endpoint:**
```
POST /api/v1/search
Body: SearchRequest
Response: ListingsResponse
```

**Tests (httpx.AsyncClient + FastAPI TestClient):**
- `test_search_structured` — POST with filters, check response shape.
- `test_search_vector` — POST with `query`, check `similarity` field.
- `test_search_pagination` — request with `limit=5`, get cursor, request next page, get different items.
- `test_search_invalid_sort` — 422.

- [ ] **Implement + test + commit.**

---

### Task 5: Metrics endpoint (GET /api/v1/metrics)

**Files:**
- Create: `src/realestate/api/routes/metrics.py`
- Modify: `src/realestate/api/app.py`
- Test: `tests/api/test_metrics_endpoint.py`

**Endpoint:**
```
GET /api/v1/metrics
Response:
{
  "total_listings": int,
  "active_listings": int,
  "by_source": {"otodom": {"active": int, "total": int}, ...},
  "last_scrape_run": {"source_id": str, "status": str, "finished_at": datetime} | null,
  "pending_enrichment": int
}
```

- [ ] **Implement + test + commit.**

---

### Task 6: CORS + middleware + error handling

**Files:**
- Modify: `src/realestate/api/app.py`

- CORS: allow `VITE_API_BASE` origin (or any in dev).
- Global exception handler: `ListingNotFound`, `ValidationError` → structured JSON error response.
- Request ID middleware (uuid per request).
- Health check: `GET /api/v1/health` → `{"status": "ok"}`.

- [ ] **Implement + test + commit.**

---

## Definition of done (Plan 5)
- `POST /api/v1/search` returns filtered, sorted, paginated listings.
- Vector search via `query` parameter returns listings with `similarity` score.
- Cursor-based pagination works correctly (stable ordering).
- `GET /api/v1/metrics` returns aggregate stats.
- `GET /api/v1/health` returns health status.
- CORS configured for frontend dev server.
- All tests pass; Ruff clean.
