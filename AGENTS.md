# AGENTS.md

Instrukcje dla agentów/developerów pracujących w tym repozytorium.

## Stack
- Python 3.14 (najnowszy stabilny), uv. Uruchamianie: `uv run <cmd>`.
- FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, pgvector.
- PostgreSQL 18 + pgvector przez docker compose (`docker compose up -d db`), obraz `pgvector/pgvector:pg18`.

## Zasady
- TDD: test → implementacja → commit.
- Lint: `uv run ruff check .` musi przechodzić.
- Brak sekretów w repo — konfiguracja przez `pydantic-settings` (`.env`).
- Migracje schematu tylko przez Alembic.

## Komendy
- Testy: `uv run pytest`
- Lint: `uv run ruff check .`
- Migracje: `uv run alembic upgrade head` — Alembic nie ładuje `.env` automatycznie, więc `EMBEDDING_DIM` musi być ustawiony jako zmienna środowiskowa przed uruchomieniem tego polecenia; wartość musi być taka sama jak przy uruchomieniu aplikacji, inaczej wymiar kolumny `listings.embedding` będzie niezgodny.
- App: `uv run uvicorn realestate.api.app:app --reload`

Specyfikacje: `docs/superpowers/specs/`. Plany: `docs/superpowers/plans/`.
