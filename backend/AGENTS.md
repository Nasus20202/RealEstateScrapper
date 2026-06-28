# Backend Instructions

Instructions for agents/developers working in `backend/`.

## Stack

- Python 3.14 (latest stable), uv. Run backend commands as `uv run <cmd>` from `backend/`.
- FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, pgvector, PostGIS.
- PostgreSQL 18.4 via docker compose (`docker compose up -d db` from the repo root), custom image `docker/db/Dockerfile` based on `postgres:18.4-trixie` with PostGIS and pgvector packages.

## Rules

- Lint: `uv run ruff check .` must pass.
- Formatting: run `uv run ruff format .` before committing backend changes.
- No secrets in repo. Backend configuration is via `pydantic-settings` and `.env`.
- Schema migrations only via Alembic.
- Current API routes are implemented at the FastAPI app root (`/health`, `/listings`, `/scrape`, `/events`, `/searches`, `/favorites`, `/settings`) and are typically exposed to the frontend behind `/api`.

## Commands

- Tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Migrations: `uv run alembic upgrade head`
- App: `uv run uvicorn realestate.api.app:app --reload`

Alembic does not load `.env` automatically, so `EMBEDDING_DIM` must be set as an environment variable before running migrations. The value must match the one used when running the application, otherwise the `listings.embedding` column dimension will be incorrect.
