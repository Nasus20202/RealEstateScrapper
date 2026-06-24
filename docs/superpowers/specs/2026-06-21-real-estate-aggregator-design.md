# Real Estate Aggregator — System Design Document

**Author:** Code (agent)
**Date:** 2026-06-21
**Status:** Draft
**Version:** 1.0

## 1. Overview

### 1.1. Purpose

The **Real Estate Aggregator** (REA) system aims to aggregate, normalize, enrich, and expose real estate listings from multiple Polish portals (Otodom, Gratka, Domiporta). The system periodically scrapes data, transforms it into a consistent schema, enriches it with AI-generated descriptions and embeddings, and provides a search API with vector-based semantic search.

### 1.2. Goals

- Aggregate listings from **3+** portals.
- Normalize heterogeneous portal data to a uniform schema.
- Detect new, changed, and removed listings incrementally.
- Enrich listings with SEO-optimized descriptions (GPT-4o-mini).
- Enable semantic search based on vector embeddings (text-embedding-3-small).
- Provide a responsive frontend (React) for searching and browsing listings.
- Expose a REST API (FastAPI) with filtering, sorting, pagination, and vector search.

### 1.3. Non-Goals

- User authentication/authorization (MVP).
- Email notifications / alerts.
- Advanced analytics / price prediction.
- Support for portals outside Poland.

## 2. Architecture

### 2.1. High-level diagram (C4 — Container)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Frontend   │────▶│  API Gateway │────▶│  PostgreSQL  │
│  (React)    │     │  (FastAPI)   │     │  + pgvector  │
└─────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────┴───────┐
                    │   Ingestion  │
                    │   Service    │
                    └──────┬───────┘
                           │
                    ┌──────┴───────┐
                    │   Scrapers   │
                    │  (plugins)   │
                    └──────────────┘
```

### 2.2. Layer overview

| Layer | Responsibility | Technology |
|-------|----------------|------------|
| Frontend | UI for search, detail, metrics | React 19, TypeScript 6, Vite 8 |
| API | REST endpoints, SSE, metrics | FastAPI, Pydantic v2, sse-starlette |
| Ingestion | Orchestration, normalization, incremental sync, enrichment | Python 3.14, SQLAlchemy 2.0 |
| Scrapers | Portal-specific data extraction | httpx, parsel (XPath/CSS), plugin registry |
| Storage | Listings, price history, metadata, vector embeddings | PostgreSQL 18.4, pgvector, PostGIS |

### 2.3. Data flow

1. **Scheduler** (APScheduler) triggers `IngestionService.ingest()` periodically (every 6h).
2. **IngestionService** iterates over registered scraper sources, for each:
   a. Runs `scraper.run_search(fetcher, criteria, max_pages)` → `list[RawListing]`.
   b. Normalizes each `RawListing` → `Listing` (via `to_listing()`), computing `raw_hash`.
   c. Executes `IncrementalEngine.sync_source()`: detects new/changed/unchanged/gone listings, updates DB.
   d. Records `ScrapeRun` with statistics.
3. **EnrichmentOrchestrator** (triggered manually or by scheduler) processes listings lacking `enriched_description` or `embedding`:
   a. Calls GPT-4o-mini for description generation.
   b. Calls text-embedding-3-small for vector embedding → stores in pgvector.
4. **User** searches via frontend → `POST /api/v1/search`:
   a. If `query` text provided → generate embedding → cosine similarity search.
   b. If structured filters only → WHERE + ORDER BY SQL.
   c. Cursor-based pagination.

## 3. Component design

### 3.1. Scrapers (plugin architecture)

**Design pattern:** Registry + abstract base class + per-portal implementations.

- `ScraperABC` defines: `source_id`, `run_search(criteria, fetcher) → list[RawListing]`.
- Each scraper registers itself via `@register_scraper` decorator.
- `RawListing` = Pydantic model with all possible fields (per source contract, some may be null).
- Fetcher abstraction (`FetcherProtocol`) enables DI for testing (real HTTP vs fixtures).

### 3.2. Storage model

#### `listings` table
| Column | Type | Description |
|--------|------|-------------|
| id | serial PK | |
| source_id | varchar(32) | "otodom", "gratka", "domiporta" |
| external_id | varchar(255) | ID from source portal |
| title | text | |
| description | text | Raw description from portal |
| enriched_description | text | GPT-generated SEO description |
| price | decimal(12,2) | |
| price_per_m2 | decimal(12,2) | Computed |
| area_m2 | float | |
| rooms | smallint | |
| floor | smallint | |
| total_floors | smallint | |
| market | varchar(16) | "primary" / "secondary" |
| status | varchar(16) | "active" / "gone" |
| city / district / street | text | |
| lat / lon | float | |
| images | text[] | |
| url | text | Canonical URL |
| posted_at | timestamptz | |
| first_seen | timestamptz | |
| last_seen | timestamptz | |
| raw_hash | varchar(64) | SHA-256 of significant fields |
| embedding | vector(768) | pgvector embedding |
| created_at | timestamptz | |
| updated_at | timestamptz | |

#### `price_history` table
| Column | Type |
|--------|------|
| id | serial PK |
| listing_id | FK → listings.id |
| price | decimal(12,2) |
| observed_at | timestamptz |

#### `scrape_runs` table
| Column | Type |
|--------|------|
| id | serial PK |
| source_id | varchar(32) |
| started_at | timestamptz |
| finished_at | timestamptz |
| status | enum (success/blocked/failed) |
| new_count / updated_count / gone_count / unchanged_count | int |
| error_message | text |

### 3.3. Incremental engine

`IncrementalEngine.sync_source(source_id, listings, now)`:

- For each incoming listing:
  - Existing? → compare `raw_hash` → unchanged (update last_seen) or updated (copy fields, reset embedding, add price_history).
  - New → insert, add price_history.
- After processing: mark missing listings as `status=gone` (only for successful runs).

### 3.4. API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/health | Health check |
| POST | /api/v1/search | Search listings (structured + vector) |
| GET | /api/v1/listings/{id} | Listing detail |
| GET | /api/v1/listings/{id}/price-history | Price history |
| GET | /api/v1/metrics | Aggregate statistics |
| POST | /api/v1/ingest | Manual ingest trigger |
| POST | /api/v1/enrich | Manual enrichment trigger |
| GET | /api/v1/events | SSE stream |

### 3.5. Frontend (React)

- **Search page:** Filter form (city, district, market, price range, etc.) + results grid + "Load more" pagination.
- **Listing detail:** Image gallery, property details, price history chart, enriched description, link to original.
- **Metrics page:** Total/active listings, per-source breakdown, last scrape status.

## 4. Quality attributes

### 4.1. Performance

- Vector search uses HNSW index on `embedding` (cosine distance).
- API responses < 200ms for typical queries (up to 100k listings).
- Cursor-based pagination prevents OFFSET performance degradation.
- Enrichment parallelized with semaphore (default concurrency: 10).

### 4.2. Resilience

- Per-source error isolation: one portal crash/block does not affect others.
- Retry logic for OpenAI API calls (3 attempts, exponential backoff).
- ScrapeRun records failures/blocks for observability.
- `apscheduler` persists jobs (optional, in-memory for MVP).

### 4.3. Security

- No secrets in repo: API keys via `pydantic-settings` + `.env`.
- Input validation via Pydantic models.
- CORS restricted to frontend origin.

## 5. Deployment

### 5.1. Local development

```
docker compose up -d db          # PostgreSQL 18.4 + pgvector + PostGIS
uv sync                          # Python dependencies
uv run alembic upgrade head      # Run migrations (requires EMBEDDING_DIM=768)
uv run uvicorn ...               # API server
pnpm dev                         # Frontend dev server
```

### 5.2. Production (future)

- Containerized backend (Dockerfile).
- Frontend static build served via CDN or nginx.
- PostgreSQL managed (e.g., Cloud SQL, RDS, or dedicated VM).
- Scheduler as Kubernetes CronJob or separate service.

## 6. Appendices

### A. Technology decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | Python 3.14 | Ecosystem, AI/ML libraries |
| ORM | SQLAlchemy 2.0 async | Mature, async-native, Alembic |
| Vector DB | pgvector | No additional infrastructure; ACID compliance |
| LLM | OpenAI GPT-4o-mini + text-embedding-3-small | Cost-effective, high quality |
| Frontend | React 19 + Vite 8 | Fast dev experience, modern tooling |
| Scheduling | APScheduler | Simple, async-native |

### B. Glossary

| Term | Definition |
|------|------------|
| RawListing | Unnormalized data from a portal scraper |
| Listing | Normalized entity in the database |
| raw_hash | SHA-256 of significant fields for change detection |
| HNSW | Hierarchical Navigable Small World — pgvector index type |
| SSE | Server-Sent Events |

---

*End of document.*
