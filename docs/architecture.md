# System Architecture

## Layers

The system is built from several clearly separated layers:

```
┌─────────────────────────────────────────────────────────────────┐
│  Scrapers (Playwright)                                          │
│  otodom · nieruchomosci-online · hossa                          │
│  Protocol: Scraper · Registry: register()                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ RawListing
┌────────────────────────────▼────────────────────────────────────┐
│  Normalization / IncrementalEngine                               │
│  raw_hash → skip duplicates → INSERT/UPDATE                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ Listing (PostgreSQL)
┌────────────────────────────▼────────────────────────────────────┐
│  Storage — PostgreSQL 18.4 + pgvector + PostGIS                  │
│  Source, Listing, PriceHistory, ScrapeRun                       │
│  LLMAnalysis, DedupGroup, DedupMember                          │
│  SavedSearch, Favorite, AppSetting                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  LLM Enrichment                                                │
│  LLMClient (OpenAI-compat / FakeLLM)                            │
│  EnrichmentService — summaries, features, embeddings            │
│  DedupService — semantic duplicate groups                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ pgvector embeddings
┌────────────────────────────▼────────────────────────────────────┐
│  Hybrid Search — SearchService                                   │
│  1. SQL filters (city, district, price, area, rooms, market)    │
│  2. pgvector top-K (cosine similarity, NL query)                │
│  3. LLM rerank (optional)                                       │
│  Degradation: no LLM → SQL filters + pgvector without rerank    │
└────────────────────────────┬────────────────────────────────────┘
                             │ JSON
┌────────────────────────────▼────────────────────────────────────┐
│  API — FastAPI                                                  │
│  REST endpoints · SSE /events (EventBus)                        │
│  Scheduler (APScheduler, SCHEDULER_ENABLED)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│  Frontend — React 18 + Vite + TypeScript                        │
│  react-router v6 · typed fetch client · plain CSS                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Component Details

### Scrapers

- Location: `backend/src/realestate/scrapers/`
- Protocol `Scraper` (structural subtyping / `typing.Protocol`): `source_id`, `display_name`, `build_search_url(criteria, page)`, `parse_search(html)`, `parse_detail(html, url)`.
- `parse_search` returns a list of `RawListing` objects (pydantic DTO).
- Registration by calling `register(scraper)` at the module level.
- Existing plugins: `otodom` (parses `__NEXT_DATA__` JSON), `nieruchomosci-online` (DOM via selectolax), `hossa` (Vue SPA — results link to investment categories, not individual listings).
- Field contract per source: [`docs/scrapers-field-contract.md`](scrapers-field-contract.md).

### Normalization and IncrementalEngine

- Each listing gets a `raw_hash` (hash of key fields) → idempotent storage.
- `IncrementalEngine` syncs scrape results with the database: new records INSERT, price changes → PriceHistory, unchanged → skip.
- Location: `backend/src/realestate/ingestion/`.

### Storage — PostgreSQL 18.4 + pgvector + PostGIS

- Schema managed by Alembic (`migrations/`); current head: `0009`.
- Column `listings.embedding` — pgvector vector. Dimension controlled by the single source of truth: `get_embedding_dim()` in `backend/src/realestate/config.py` (default 2048). The dimension **must** match between migration and application runtime.
- Column `listings.geom` — PostGIS point (`geometry(Point, 4326)`) synced by trigger from `lat/lon`; GiST index powers map aggregations.
- Endpoint `/listings/map/hexes` uses PostGIS (`ST_HexagonGrid`, `ST_Transform`, `ST_Intersects`, `ST_AsGeoJSON`) to build a hexagonal heatmap of average prices and listing counts.
- SQLAlchemy 2.0 async models: `Source`, `Listing`, `PriceHistory`, `ScrapeRun`, `LLMAnalysis`, `DedupGroup`, `DedupMember`, `SavedSearch`, `Favorite`, `AppSetting`.
- Model location: package `backend/src/realestate/models/` (files `base.py`, `listing.py`, `source.py`, `scrape_run.py`, `llm_analysis.py`, `dedup.py`, `user_data.py`); `Base` exported from `realestate.models`.

### LLM Enrichment

- `LLMClient` — OpenAI-compatible client (defaults to OpenRouter). Can be replaced by `FakeLLM` in tests.
- `EnrichmentService` — generates summaries (`LLMAnalysis.summary`), features (`LLMAnalysis.features`), computes embeddings and saves them as pgvector.
- `DedupService` — groups semantic duplicates into `DedupGroup`/`DedupMember` tables.
- LLM is disabled (degradation) when none of `LLM_API_KEY` + `LLM_MODEL` + `LLM_EMBEDDING_MODEL` are set.
- Location: `backend/src/realestate/enrichment/`, `backend/src/realestate/llm/`.

### Hybrid Search — SearchService

Search proceeds in three stages:

1. **SQL filters** — filter by city, district, price, area, rooms, market type.
2. **pgvector top-K** — when a `q` query (natural language) is provided, compute the query embedding and sort by cosine similarity.
3. **LLM rerank** — (optional) re-rank top-K results via LLM.

Degradation: when LLM is unavailable, skip step 3. When embeddings are missing, skip step 2 and return purely SQL-based results.

Location: `backend/src/realestate/search/`.

### FastAPI API

Endpoints:

- `GET /health` — health check
- `GET /listings` — list with filters (city, district, min/max price/area/rooms, market, q, limit, offset) → `{items, total}`
- `GET /listings/{id}` — details + price_history + summary/features + duplicate_listing_ids
- `GET /stats` — listing statistics: overview, aggregations per district/source/city/market, rooms and price buckets
- `GET /listings/map/points`, `GET /listings/map/hexes` — map points and hexes filtered by current viewport/bbox
- `POST /scrape`, `GET /scrape/runs`, `GET /scrape/runs/{id}` — scrape management
- `GET /events` — SSE: real-time scrape progress
- `GET /searches`, `POST /searches`, `DELETE /searches/{id}` — saved searches
- `GET /favorites`, `POST /favorites`, `DELETE /favorites/{listing_id}` — favorites
- `GET /settings`, `PUT /settings` — application config (API key is never returned)

Location: `backend/src/realestate/api/`.

### Scheduler

- APScheduler started in FastAPI lifespan when `SCHEDULER_ENABLED=true`.
- Default interval: `SCHEDULER_DEFAULT_INTERVAL_MINUTES` (default 360).

### Frontend

- Location: `frontend/` (standalone pnpm project).
- React 18 + Vite 8 + TypeScript 6 + react-router v6.
- Typed fetch client; plain CSS; Vitest 4 + Testing Library + MSW + jsdom 29.
- Listing list has three views: default grid, compact tile, and full-width list with description and extra details.
- Map loads points and hexes only for the visible viewport (`north/south/east/west`), instead of fetching a fixed limit of listings from the entire area.
- Environment variable: `VITE_API_BASE` (default `http://localhost:8000`).
