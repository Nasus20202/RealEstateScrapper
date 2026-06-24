# AGENTS.md

Instructions for agents/developers working in this repository.

## Stack

- Python 3.14 (latest stable), uv. Run: `uv run <cmd>` (from `backend/` directory).
- FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, pgvector, PostGIS.
- PostgreSQL 18.4 via docker compose (`docker compose up -d db`), custom image `docker/db/Dockerfile` based on `postgres:18.4-trixie` with PostGIS and pgvector packages.

## Rules

- TDD: test → implementation → commit.
- Lint: `uv run ruff check .` must pass.
- No secrets in repo — configuration via `pydantic-settings` (`.env`).
- Schema migrations only via Alembic.
- Keep OpenSpec and implementation aligned; do not treat legacy `docs/superpowers/` plans as the source of truth.

## Commands

- Tests: `uv run pytest` (run from `backend/` directory)
- Lint: `uv run ruff check .` (run from `backend/` directory)
- Migrations: `uv run alembic upgrade head` — Alembic does not load `.env` automatically, so `EMBEDDING_DIM` must be set as an environment variable before running this command; the value must match the one used when running the application, otherwise the `listings.embedding` column dimension will be incorrect.
- App: `uv run uvicorn realestate.api.app:app --reload`

## OpenSpec

- Canonical capability specs live in `openspec/specs/`.
- Validate spec changes with `openspec validate --specs`.
- `docs/superpowers/` is a legacy archive; see `docs/superpowers/README.md` for the migration mapping.
- Keep specs grounded in actual shipped behavior unless the user is explicitly proposing a new change.
- Current API routes are implemented at the FastAPI app root (`/health`, `/listings`, `/scrape`, `/events`, `/searches`, `/favorites`, `/settings`) and are typically exposed to the frontend behind `/api`.

Documentation: `docs/`

## Frontend

Frontend is a standalone project in the `frontend/` directory (React 19 + Vite 8 + TypeScript 6 + react-router v6).

- Install: `pnpm install`
- Dev server: `pnpm --dir frontend dev`
- Production build: `pnpm --dir frontend build` (= `tsc -b && vite build`)
- Tests: `pnpm --dir frontend exec vitest run` (Vitest 4 + Testing Library + MSW + jsdom 29)
- API base defaults to `/api`; nginx and Vite dev server proxy it to the backend. `VITE_API_BASE` can override this for custom deployments.

## Documentation

Full technical documentation for the project:

- [`README.md`](README.md) — project overview, quick start, links to docs/
- [`openspec/specs/`](openspec/specs/) — canonical capability specs
- [`docs/architecture.md`](docs/architecture.md) — layered architecture and data flow
- [`docs/running.md`](docs/running.md) — full setup instructions (requirements, database, migrations, API, frontend)
- [`docs/configuration.md`](docs/configuration.md) — all configuration variables (Settings)
- [`docs/adding-a-scraper.md`](docs/adding-a-scraper.md) — how to add a new scraper plugin
- [`docs/testing.md`](docs/testing.md) — test strategy, markers, lint, frontend
- [`docs/scrapers-field-contract.md`](docs/scrapers-field-contract.md) — RawListing field contract per source
- [`docs/superpowers/README.md`](docs/superpowers/README.md) — legacy superpowers to OpenSpec migration note
