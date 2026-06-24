# Real Estate Listing Aggregator (Tricity)

Aggregates apartment listings from real estate portals in the Tricity area (Gdańsk, Gdynia, Sopot). Scrapes listings, enriches them with LLM-generated summaries and features, and provides a hybrid search API with a React frontend.

---

## Architecture

Detailed layer description: [`docs/architecture.md`](docs/architecture.md).

Quick overview:

1. **Scrapers** — Playwright plugins (`otodom`, `nieruchomosci-online`, `hossa`), `Scraper` protocol, `register()` registry.
2. **Normalization** — unique `raw_hash`, write to PostgreSQL via `IncrementalEngine`.
3. **LLM Enrichment** — `EnrichmentService` (summaries, features), `DedupService` (duplicate groups), pgvector embeddings.
4. **Hybrid Search** — `SearchService`: SQL filters → pgvector top-K → LLM rerank; degradation when LLM unavailable.
5. **API** — FastAPI REST + SSE (`/events`), APScheduler scheduler.
6. **Frontend** — React 19 + Vite 8 + TypeScript 6 SPA.

---

## Running

### Fastest: full stack via Docker Compose

Requires only Docker. Sets up the database (PostgreSQL 18.4 + pgvector + PostGIS), backend (FastAPI + Playwright, migrations run automatically) and frontend (nginx):

```bash
docker compose up -d --build
# Frontend: http://localhost:8080   API proxy: http://localhost:8080/api   (health: /api/health)
```

LLM is optional (without a key, rule-based ranking is used). To enable, add `LLM_API_KEY`/`LLM_MODEL`/`LLM_EMBEDDING_MODEL` to your `.env` file (Compose loads it automatically). Details: [`docs/running.md`](docs/running.md).

### Local development (with hot-reload)

Short guide for the dev environment. Full documentation: [`docs/running.md`](docs/running.md).

```bash
# 1. Database
docker compose up -d db

# 2. Migrations (EMBEDDING_DIM must be set as an environment variable)
cd backend
EMBEDDING_DIM=2048 uv run alembic upgrade head

# 3. Backend
uv run uvicorn realestate.api.app:app --reload

# 4. Frontend (in a separate terminal)
pnpm install && pnpm --dir frontend dev
```

---

## Configuration

Detailed variable description: [`docs/configuration.md`](docs/configuration.md).

Configuration via `.env` file (template: `.env.example`) and environment variables. An LLM key (`LLM_API_KEY`) is required for enrichment — without it the system runs in degraded mode (no embeddings or reranking). `GET /settings` **never** returns `LLM_API_KEY`, only the `llm_api_key_set` field (boolean).

---

## Tests

```bash
# Backend
cd backend
uv run pytest
uv run ruff check .

# Frontend (from frontend/ directory)
pnpm --dir frontend exec vitest run
pnpm --dir frontend build
```

Backend tests require Docker (testcontainers starts pg18+pgvector; PostGIS is no-op in this test image). Details: [`docs/testing.md`](docs/testing.md).

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — layered architecture, data flow
- [`docs/running.md`](docs/running.md) — full setup instructions (requirements, database, migrations, API, frontend)
- [`docs/configuration.md`](docs/configuration.md) — all configuration variables
- [`docs/adding-a-scraper.md`](docs/adding-a-scraper.md) — how to add a new scraper plugin
- [`docs/testing.md`](docs/testing.md) — test strategy, markers, lint
- [`docs/scrapers-field-contract.md`](docs/scrapers-field-contract.md) — `RawListing` field contract per source
