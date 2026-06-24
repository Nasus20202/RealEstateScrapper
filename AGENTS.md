# AGENTS.md

Instrukcje dla agentów/developerów pracujących w tym repozytorium.

## Stack

- Python 3.14 (najnowszy stabilny), uv. Uruchamianie: `uv run <cmd>` (z katalogu `backend/`).
- FastAPI, SQLAlchemy 2.0 async + asyncpg, Alembic, pgvector, PostGIS.
- PostgreSQL 18.4 przez docker compose (`docker compose up -d db`), własny obraz `docker/db/Dockerfile` na bazie `postgres:18.4-trixie` z pakietami PostGIS i pgvector.

## Zasady

- TDD: test → implementacja → commit.
- Lint: `uv run ruff check .` musi przechodzić.
- Brak sekretów w repo — konfiguracja przez `pydantic-settings` (`.env`).
- Migracje schematu tylko przez Alembic.

## Komendy

- Testy: `uv run pytest` (uruchamiać z katalogu `backend/`)
- Lint: `uv run ruff check .` (uruchamiać z katalogu `backend/`)
- Migracje: `uv run alembic upgrade head` — Alembic nie ładuje `.env` automatycznie, więc `EMBEDDING_DIM` musi być ustawiony jako zmienna środowiskowa przed uruchomieniem tego polecenia; wartość musi być taka sama jak przy uruchomieniu aplikacji, inaczej wymiar kolumny `listings.embedding` będzie niezgodny.
- App: `uv run uvicorn realestate.api.app:app --reload`

Specyfikacje: `docs/superpowers/specs/`. Plany: `docs/superpowers/plans/`.

## Frontend

Frontend to samodzielny projekt w katalogu `frontend/` (React 19 + Vite 8 + TypeScript 6 + react-router v6).

- Instalacja: `pnpm install`
- Dev server: `pnpm --dir frontend dev`
- Build produkcyjny: `pnpm --dir frontend build` (= `tsc -b && vite build`)
- Testy: `pnpm --dir frontend exec vitest run` (Vitest 4 + Testing Library + MSW + jsdom 29)
- Zmienna środowiskowa: `VITE_API_BASE` — adres backendu (domyślnie `http://localhost:8000`)

## Dokumentacja

Pełna dokumentacja techniczna projektu:

- [`README.md`](README.md) — przegląd projektu, szybki start, linki do docs/
- [`docs/architecture.md`](docs/architecture.md) — architektura warstw i przepływ danych
- [`docs/running.md`](docs/running.md) — pełna instrukcja uruchomienia (wymagania, baza, migracje, API, frontend)
- [`docs/configuration.md`](docs/configuration.md) — wszystkie zmienne konfiguracyjne (Settings)
- [`docs/adding-a-scraper.md`](docs/adding-a-scraper.md) — jak dodać nową wtyczkę scrapera
- [`docs/testing.md`](docs/testing.md) — strategia testów, markery, lint, frontend
- [`docs/scrapers-field-contract.md`](docs/scrapers-field-contract.md) — kontrakt pól RawListing per źródło
