# Uruchomienie środowiska deweloperskiego

## Wymagania

- **Python 3.14** + **uv** — menedżer pakietów i środowisk wirtualnych.
- **Node.js 20+** (do frontendu; rozwijane na Node 26) — `npm` wbudowane.
- **Docker** — do uruchomienia bazy danych PostgreSQL (i testów integracyjnych via testcontainers).

---

## 0. Najszybszy start: cały stack przez Docker Compose

Jednym poleceniem stawiasz bazę (pgvector pg18), backend (FastAPI + Playwright) i frontend (nginx). Wymaga tylko Dockera (nie potrzebujesz lokalnie Pythona/Node):

```bash
docker compose up -d --build
```

Serwisy:

| Serwis | URL | Opis |
| --- | --- | --- |
| `web` | http://localhost:8080 | Frontend SPA (nginx) |
| `api` | http://localhost:8000 | REST API + SSE; migracje uruchamiane automatycznie przy starcie |
| `db`  | localhost:5432 | PostgreSQL 18 + pgvector (wolumen `pgdata`) |

Sprawdzenie: `curl http://localhost:8000/health` → `{"status":"ok","database":true}`, a w przeglądarce `http://localhost:8080`.

**LLM (opcjonalnie).** Bez klucza aplikacja działa w trybie degradacji (ranking regułowy). Aby włączyć LLM, utwórz plik `.env` w katalogu projektu (Docker Compose ładuje go automatycznie do interpolacji zmiennych):

```bash
LLM_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-4o-mini
LLM_EMBEDDING_MODEL=openai/text-embedding-3-small
# opcjonalnie: SCHEDULER_ENABLED=true, SCHEDULER_DEFAULT_INTERVAL_MINUTES=360
# opcjonalnie: CORS_ALLOW_ORIGINS=http://localhost:8080  (domyślnie "*")
```

> **Uwaga o embeddingu:** `EMBEDDING_DIM` (domyślnie 1536) musi pasować do modelu embeddingów. Jeśli go zmienisz po pierwszym uruchomieniu, usuń wolumen i zbuduj schemat na nowo: `docker compose down -v && docker compose up -d --build`.

Zatrzymanie: `docker compose down` (zachowuje dane) lub `docker compose down -v` (usuwa wolumen z danymi).

Pozostałe sekcje opisują uruchomienie **lokalne bez Dockera** (wygodne do dewelopmentu z hot-reload).

---

## 1. Baza danych

Projekt używa obrazu `pgvector/pgvector:pg18` (PostgreSQL 18 z rozszerzeniem pgvector).

```bash
docker compose up -d db
```

Domyślne połączenie: `postgresql+asyncpg://realestate:realestate@localhost:5432/realestate`.

---

## 2. Zmienne środowiskowe

Skopiuj plik przykładowy i uzupełnij wartości:

```bash
cp .env.example .env
# edytuj .env — przynajmniej DATABASE_URL musi być ustawiony
```

Minimalne `.env` do uruchomienia bez LLM:

```
DATABASE_URL=postgresql+asyncpg://realestate:realestate@localhost:5432/realestate
EMBEDDING_DIM=1536
```

Szczegóły wszystkich zmiennych: [`docs/configuration.md`](configuration.md).

---

## 3. Instalacja zależności

```bash
uv sync --extra dev
```

---

## 4. Migracje bazy danych

**Ważne:** Alembic **nie ładuje `.env` automatycznie**. Przed uruchomieniem migracji `EMBEDDING_DIM` musi być ustawiony jako zmienna środowiskowa i musi mieć tę samą wartość, co przy uruchomieniu aplikacji. Niezgodność wymiaru powoduje błąd przy zapisie embeddingów.

```bash
EMBEDDING_DIM=1536 uv run alembic upgrade head
```

Aktualny migration head: `0007`.

---

## 5. Uruchomienie API (backend)

```bash
uv run uvicorn realestate.api.app:app --reload
```

API dostępne pod: `http://localhost:8000`

Dokumentacja OpenAPI: `http://localhost:8000/docs`

---

## 6. Uruchomienie frontendu

Frontend to samodzielny projekt w katalogu `frontend/`.

```bash
cd frontend
npm install
npm run dev
```

Frontend dostępny pod: `http://localhost:5173`

Zmienna środowiskowa `VITE_API_BASE` określa adres backendu (domyślnie `http://localhost:8000`). Przykład zmiany:

```bash
VITE_API_BASE=http://localhost:9000 npm run dev
```

---

## 7. Uruchomienie scrapera

Po uruchomieniu backendu wyślij żądanie POST:

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"city": "Gdańsk"}'
```

Postęp scrapowania w czasie rzeczywistym przez SSE:

```bash
curl http://localhost:8000/events
```

Status scrapowania:

```bash
curl http://localhost:8000/scrape/runs
```

---

## 8. Scheduler (opcjonalny)

Aby automatycznie uruchamiać scraping cyklicznie, ustaw w `.env`:

```
SCHEDULER_ENABLED=true
SCHEDULER_DEFAULT_INTERVAL_MINUTES=360
```

Scheduler startuje w lifespan FastAPI i zatrzymuje się przy zamknięciu aplikacji.

---

## 9. Szybki start (all-in-one)

```bash
# Terminal 1 — baza danych
docker compose up -d db

# Terminal 2 — backend
EMBEDDING_DIM=1536 uv run alembic upgrade head
uv run uvicorn realestate.api.app:app --reload

# Terminal 3 — frontend
cd frontend && npm install && npm run dev
```
