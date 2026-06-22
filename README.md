# Agregator ofert nieruchomości (Trójmiasto)

Lokalna aplikacja agregująca oferty mieszkań z wielu portali nieruchomości w Trójmieście (Gdańsk, Gdynia, Sopot). Pipeline: scraping Playwright → normalizacja z deduplikacją (`raw_hash`) → PostgreSQL 18.4 + pgvector + PostGIS → wzbogacanie LLM (podsumowania, cechy, embeddingi, dedup) → wyszukiwanie hybrydowe (filtry SQL → pgvector top-K → rerank LLM) i agregacje mapowe PostGIS → FastAPI REST + SSE → React/Vite/TS SPA.

---

## Architektura

Szczegółowy opis warstw: [`docs/architecture.md`](docs/architecture.md).

Krótki przegląd:

1. **Scrapery** — wtyczki Playwright (`otodom`, `nieruchomosci-online`, `hossa`), protokół `Scraper`, rejestr `register()`.
2. **Normalizacja** — unikalne `raw_hash`, zapis do PostgreSQL przez `IncrementalEngine`.
3. **Wzbogacanie LLM** — `EnrichmentService` (podsumowania, cechy), `DedupService` (grupy duplikatów), embeddingi pgvector.
4. **Wyszukiwanie hybrydowe** — `SearchService`: filtry SQL → pgvector top-K → LLM rerank; degradacja przy braku LLM.
5. **API** — FastAPI REST + SSE (`/events`), scheduler APScheduler.
6. **Frontend** — React 19 + Vite 8 + TypeScript 6 SPA.

---

## Uruchomienie

### Najszybciej: cały stack przez Docker Compose

Wymaga tylko Dockera. Stawia bazę (PostgreSQL 18.4 + pgvector + PostGIS), backend (FastAPI + Playwright, migracje uruchamiane automatycznie) i frontend (nginx):

```bash
docker compose up -d --build
# Frontend: http://localhost:8080   API: http://localhost:8000   (health: /health)
```

LLM jest opcjonalny (bez klucza działa ranking regułowy). Aby włączyć, dodaj `LLM_API_KEY`/`LLM_MODEL`/`LLM_EMBEDDING_MODEL` do pliku `.env` (Compose ładuje go automatycznie). Szczegóły: [`docs/running.md`](docs/running.md).

### Lokalnie (dev, z hot-reload)

Skrócona instrukcja dla środowiska deweloperskiego. Pełna dokumentacja: [`docs/running.md`](docs/running.md).

```bash
# 1. Baza danych
docker compose up -d db

# 2. Migracje (EMBEDDING_DIM musi być ustawiony jako zmienna środowiskowa)
cd backend
EMBEDDING_DIM=2048 uv run alembic upgrade head

# 3. Backend
uv run uvicorn realestate.api.app:app --reload

# 4. Frontend (w osobnym terminalu)
pnpm install && pnpm --dir frontend dev
```

---

## Konfiguracja

Szczegółowy opis zmiennych: [`docs/configuration.md`](docs/configuration.md).

Konfiguracja przez plik `.env` (wzór: `.env.example`) i zmienne środowiskowe. Klucz LLM (`LLM_API_KEY`) jest wymagany do wzbogacania — bez niego system działa w trybie degradacji (bez embeddingów i rerankowania). `GET /settings` **nigdy** nie zwraca `LLM_API_KEY`, tylko pole `llm_api_key_set` (boolean).

---

## Testy

```bash
# Backend
cd backend
uv run pytest
uv run ruff check .

# Frontend (z katalogu frontend/)
pnpm --dir frontend exec vitest run
pnpm --dir frontend build
```

Testy backendowe wymagają Dockera (testcontainers uruchamia pg18+pgvector; PostGIS jest no-op w tym obrazie testowym). Szczegóły: [`docs/testing.md`](docs/testing.md).

---

## Dokumentacja

- [`docs/architecture.md`](docs/architecture.md) — architektura warstw, przepływ danych
- [`docs/running.md`](docs/running.md) — pełna instrukcja uruchomienia (wymagania, baza, migracje, API, frontend)
- [`docs/configuration.md`](docs/configuration.md) — wszystkie zmienne konfiguracyjne
- [`docs/adding-a-scraper.md`](docs/adding-a-scraper.md) — jak dodać nową wtyczkę scrapera
- [`docs/testing.md`](docs/testing.md) — strategia testów, markery, lint
- [`docs/scrapers-field-contract.md`](docs/scrapers-field-contract.md) — kontrakt pól `RawListing` per źródło
