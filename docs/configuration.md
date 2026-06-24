# Configuration

Application configuration uses environment variables or a `.env` file in the project root directory (template: `.env.example`). The `Settings` class in `backend/src/realestate/config.py` uses `pydantic-settings` for validation and loading.

**Secrets (e.g. `LLM_API_KEY`) must never be committed to the repository.** Use only `.env` (locally) or environment variables (CI/production). `GET /settings` **never** returns the `LLM_API_KEY` value — it only returns the `llm_api_key_set` (boolean) field.

---

## Database

| Variable         | Required | Default | Description                                                                                                                                                |
| --------------- | -------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`  | **yes**  | —       | asyncpg connection URL, e.g. `postgresql+asyncpg://user:pass@localhost:5432/dbname`                                                                         |
| `EMBEDDING_DIM` | no       | `2048`  | pgvector vector dimension. **Must be identical for migrations and application runtime.** Single source of truth: `get_embedding_dim()` in `config.py`.       |

> **Note:** Alembic does not load `.env`. Before `alembic upgrade head`, set `EMBEDDING_DIM` as a real environment variable:
>
> ```bash
> EMBEDDING_DIM=2048 uv run alembic upgrade head
> ```

---

## Scraper

| Variable                    | Default              | Description                                   |
| --------------------------- | -------------------- | --------------------------------------------- |
| `SCRAPER_USER_AGENT`        | `Mozilla/5.0 …`      | User-Agent for Playwright                     |
| `SCRAPER_MIN_DELAY_SECONDS` | `1.5`                | Minimum delay between requests (seconds)      |
| `SCRAPER_NAV_TIMEOUT_MS`    | `30000`              | Playwright navigation timeout (ms)            |
| `SCRAPER_WAIT_UNTIL`        | `domcontentloaded`   | Page readiness condition (`load`, `domcontentloaded`, `networkidle`) |

---

## Geocoding (map)

Scraper data does not include coordinates, so the listing address (street/district/city) is geocoded **during ingestion** and stored in the `listings.lat`/`listings.lon` columns. This ensures listings appear as pins on the map in the frontend. The default provider is [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org) (free, no API key required). Geocoding is **best-effort** — an error or missing result does not stop scraping (the listing simply has no pin).

| Variable                      | Default                                | Description                                                                             |
| ----------------------------- | -------------------------------------- | --------------------------------------------------------------------------------------- |
| `GEOCODING_ENABLED`           | `true`                                 | Enable address geocoding during ingestion (`true`/`false`). Disabling skips map pins.   |
| `GEOCODING_BASE_URL`          | `https://nominatim.openstreetmap.org`  | Base URL of the geocoding service (Nominatim-compatible API).                           |
| `GEOCODING_USER_AGENT`        | `RealEstateAggregator/1.0 (local tool)`| User-Agent required by Nominatim policy.                                                |
| `GEOCODING_MIN_DELAY_SECONDS` | `1.0`                                  | Minimum delay between requests (throttling — Nominatim requires ≤ 1 req/s).             |
| `GEOCODING_TIMEOUT_SECONDS`   | `10.0`                                 | Single geocoding request timeout (seconds).                                             |

> **Note:** results are cached in-memory by address, so re-scraping the same listings does not query the service again. For large volumes, consider running your own Nominatim instance (`GEOCODING_BASE_URL`).

---

## LLM

The application uses an OpenAI-compatible API. Default provider: [OpenRouter](https://openrouter.ai). LLM is **disabled** (degradation mode) if not **all three** are set: `LLM_API_KEY`, `LLM_MODEL`, `LLM_EMBEDDING_MODEL`.

| Variable              | Default                       | Description                                                                    |
| --------------------- | ----------------------------- | ------------------------------------------------------------------------------ |
| `LLM_BASE_URL`        | `https://openrouter.ai/api/v1`| Base API URL (OpenAI-compatible)                                               |
| `LLM_API_KEY`         | `None`                        | API key (secret — `.env` only, never returned by API)                          |
| `LLM_MODEL`           | `None`                        | Text generation model (e.g. `openai/gpt-4o-mini`)                              |
| `LLM_EMBEDDING_MODEL` | `None`                        | Embedding model (e.g. `openai/text-embedding-3-small`)                         |
| `LLM_TIMEOUT_SECONDS` | `30.0`                        | Request timeout to LLM (seconds)                                               |
| `LLM_MAX_RETRIES`     | `2`                           | Retry count on LLM error                                                       |

When LLM is disabled, the system operates with degradation:

- No summaries or features (`LLMAnalysis`).
- No embeddings → no pgvector semantic search.
- No result reranking.
- Search still works via SQL filters.

---

## Scheduler

Scheduler (APScheduler) settings:

| Variable                             | Default | Description                                                |
| ------------------------------------ | ------- | ---------------------------------------------------------- |
| `SCHEDULER_ENABLED`                  | `false` | Enable automatic periodic scraping (`true`/`false`)        |
| `SCHEDULER_DEFAULT_INTERVAL_MINUTES` | `360`   | Interval between scrapes (minutes)                         |

When `SCHEDULER_ENABLED=true`, APScheduler starts in the FastAPI lifespan.

---

## API / CORS

| Variable              | Default | Description                                                                                                                     |
| --------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `CORS_ALLOW_ORIGINS`  | `*`     | Allowed CORS origins for the API (comma-separated list or `*`). Needed when the frontend is served from a different origin than the API (e.g. `web` on `:8080` calling API on `:8000`). |

---

## Example `.env` File

```dotenv
# Required
DATABASE_URL=postgresql+asyncpg://realestate:realestate@localhost:5432/realestate

# Recommended (must match migration)
EMBEDDING_DIM=2048

# LLM — optional, but required for enrichment and semantic search
LLM_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-4o-mini
LLM_EMBEDDING_MODEL=openai/text-embedding-3-small

# Scheduler — disabled by default
# SCHEDULER_ENABLED=true
# SCHEDULER_DEFAULT_INTERVAL_MINUTES=360

# Geocoding — enabled by default (Nominatim/OSM). Disable to skip pins.
# GEOCODING_ENABLED=false
```
