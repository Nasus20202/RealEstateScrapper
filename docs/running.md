# Running the Development Environment

## Requirements

- **Python 3.14** + **uv** — package and virtual environment manager.
- **Node.js 22+** and **pnpm** (for the frontend; Vite 8 requires modern Node; Docker uses Corepack + pnpm 10.23.0).
- **Docker** — to run the PostgreSQL database (and integration tests via testcontainers).

---

## 0. Quickest Start: Full Stack via Docker Compose

With a single command you get the database (PostgreSQL 18.4 + pgvector + PostGIS), backend (FastAPI + Playwright) and frontend (nginx). Requires only Docker (no local Python/Node needed):

```bash
docker compose up -d --build
```

Services:

| Service | URL                   | Description                                                   |
| ------- | --------------------- | ------------------------------------------------------------- |
| `web`   | http://localhost:8080 | Frontend SPA (nginx) + `/api` reverse proxy                   |
| `api`   | http://localhost:8000 | Direct REST API + SSE; migrations run automatically at startup|
| `db`    | localhost:5432        | PostgreSQL 18.4 + pgvector + PostGIS (volume `pgdata`)        |

Verify: `curl http://localhost:8080/api/health` → `{"status":"ok","database":true}`, and in the browser `http://localhost:8080`. OpenAPI docs are available through nginx at `http://localhost:8080/api/docs`. The backend remains directly reachable at `http://localhost:8000` in the default Compose setup.

**LLM (optional).** Without a key the app runs in degradation mode (rule-based ranking). To enable LLM, create a `.env` file in the project root (Docker Compose loads it automatically for variable interpolation):

```bash
LLM_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-4o-mini
LLM_EMBEDDING_MODEL=openai/text-embedding-3-small
# optional: SCHEDULER_ENABLED=true, SCHEDULER_DEFAULT_INTERVAL_MINUTES=360
# optional: CORS_ALLOW_ORIGINS=http://localhost:8080  (default "*")
```

> **Note on embeddings:** `EMBEDDING_DIM` (default 2048) must match the embedding model. If you change it after the first run, remove the volume and rebuild the schema: `docker compose down -v && docker compose up -d --build`.

Shutdown: `docker compose down` (preserves data) or `docker compose down -v` (removes data volume).

The remaining sections describe **local setup without Docker** (convenient for development with hot-reload).

---

## 1. Database

The project builds its own image from `docker/db/Dockerfile` based on `postgres:18.4-trixie` and installs `postgresql-18-postgis-3` and `postgresql-18-pgvector`.

```bash
docker compose up -d db
```

Default connection: `postgresql+asyncpg://realestate:realestate@localhost:5432/realestate`.

---

## 2. Environment Variables

Copy the sample file and fill in the values:

```bash
cp .env.example .env
# edit .env — at least DATABASE_URL must be set
```

Minimal `.env` to run without LLM:

```
DATABASE_URL=postgresql+asyncpg://realestate:realestate@localhost:5432/realestate
EMBEDDING_DIM=2048
```

Details of all variables: [`docs/configuration.md`](configuration.md).

---

## 3. Install Dependencies

```bash
cd backend
uv sync --extra dev
```

---

## 4. Database Migrations

**Important:** Alembic **does not load `.env` automatically**. Before running migrations, `EMBEDDING_DIM` must be set as an environment variable with the same value used when running the application. Dimension mismatch causes an error when saving embeddings. The PostGIS migration adds `listings.geom`, a GiST index, and a trigger syncing `geom` from `lat/lon`.

```bash
cd backend
EMBEDDING_DIM=2048 uv run alembic upgrade head
```

Current migration head: `0009`.

---

## 5. Running the API (backend)

```bash
cd backend
uv run uvicorn realestate.api.app:app --reload
```

API available at: `http://localhost:8000`

OpenAPI docs: `http://localhost:8000/docs`

---

## 6. Running the Frontend

The frontend is a pnpm workspace in the `frontend/` directory.

Frontend stack: React 18, Vite 8, `@vitejs/plugin-react` 6, TypeScript 6, ESLint 10, Vitest 4 and jsdom 29.

```bash
pnpm install
pnpm --dir frontend dev
```

Frontend available at: `http://localhost:5173`

The frontend defaults to the same-origin `/api` path. In Docker, nginx forwards `/api/...` to the backend container and strips the `/api` prefix. In local Vite development, `vite.config.ts` proxies `/api` to `http://localhost:8000`.

Use `VITE_API_BASE` only for custom overrides. Example:

```bash
VITE_API_BASE=http://localhost:9000 pnpm --dir frontend dev
```

---

## 7. Running the Scraper

After starting the backend, send a POST request:

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"city": "Gdańsk"}'
```

Real-time scraping progress via SSE:

```bash
curl http://localhost:8000/events
```

Scraping status:

```bash
curl http://localhost:8000/scrape/runs
```

---

## 8. Scheduler (optional)

To automatically run scraping periodically, set in `.env`:

```
SCHEDULER_ENABLED=true
SCHEDULER_DEFAULT_INTERVAL_MINUTES=360
```

The scheduler starts in the FastAPI lifespan and stops when the application shuts down.

---

## 9. Quick Start (all-in-one)

```bash
# Terminal 1 — database
docker compose up -d db

# Terminal 2 — backend
cd backend
EMBEDDING_DIM=2048 uv run alembic upgrade head
uv run uvicorn realestate.api.app:app --reload

# Terminal 3 — frontend
pnpm install && pnpm --dir frontend dev
```
