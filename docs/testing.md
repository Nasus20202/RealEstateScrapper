# Strategia testów

## Backend

### Uruchomienie

```bash
uv run pytest
```

### Konfiguracja

- Framework: **pytest** z pluginem **pytest-asyncio** (tryb `auto` — wszystkie testy async uruchamiane automatycznie).
- Testy integracyjne i E2E używają **testcontainers** do uruchomienia PostgreSQL 18 + pgvector w izolowanym kontenerze Docker. **Wymagany Docker.**
- Konfiguracja pytest: `pyproject.toml` (sekcja `[tool.pytest.ini_options]`).

### Struktura testów

```
tests/
├── conftest.py              # Fixtures globalne (baza, silnik, sesja)
├── test_config.py           # Testy konfiguracji (Settings)
├── test_smoke.py            # Smoke testy (import, zdrowie)
├── test_docs_present.py     # Obecność plików dokumentacji
├── api/                     # Testy HTTP endpointów (FastAPI TestClient)
├── db/                      # Testy modeli i migracji
├── e2e/                     # Testy end-to-end przez HTTP na realnej pg18
├── enrichment/              # Testy EnrichmentService, DedupService
├── events/                  # Testy EventBus / SSE
├── fixtures/data/           # Spakowane (gzip) HTML fixtures dla scraperów
├── ingestion/               # Testy IncrementalEngine
├── llm/                     # Testy LLMClient, FakeLLM
├── repositories/            # Testy warstwy dostępu do danych
├── scheduler/               # Testy harmonogramu
├── scrapers/                # Testy offline wtyczek scraperów
└── search/                  # Testy SearchService (hybrydowe wyszukiwanie)
```

### Markery

Testy oznaczone `@pytest.mark.live` wymagają zewnętrznego dostępu sieciowego (np. prawdziwe scraping) i są domyślnie pominięte. Uruchom je jawnie:

```bash
uv run pytest -m live
```

### Testcontainers i Docker

Testy integracyjne uruchamiają kontener `pgvector/pgvector:pg18` przez testcontainers. Kontener startuje raz per sesja pytest (fixture o zasięgu `session`). Wymagane:

1. Działający Docker daemon.
2. Dostęp do Docker Hub (lub lokalny obraz `pgvector/pgvector:pg18`).

Przy pierwszym uruchomieniu Docker pobiera obraz — może to potrwać chwilę.

### Lint

```bash
uv run ruff check .
```

Ruff musi być czysty przed każdym commitem. Konfiguracja: `pyproject.toml` (sekcja `[tool.ruff]`).

### Pyright / type-checking

**Znane false-positives:** Pyright zgłasza błędy importów dla projektów z układem `src/` (src-layout). Te błędy są fałszywe alerty — nie blokują działania. **Bramka jakości** to ruff + pytest, nie Pyright.

---

## Frontend

### Uruchomienie testów

```bash
cd frontend
npm test -- --run
```

Flaga `--run` uruchamia vitest w trybie jednorazowym (nie watch).

### Konfiguracja

- Framework: **vitest** + **@testing-library/react** + **MSW** (Mock Service Worker do mockowania API).
- Środowisko: jsdom.
- TypeScript: tsc nie blokuje testów, ale `npm run build` (= `tsc -b && vite build`) musi przechodzić.

### Build

```bash
cd frontend
npm run build
```

Build weryfikuje poprawność TypeScript i generuje artefakty produkcyjne w `frontend/dist/`.

### Struktura testów

Testy są umieszczone obok komponentów w `frontend/src/` lub w `frontend/src/__tests__/`. MSW `handlers` mockują endpointy backendowe — testy frontendu nie wymagają uruchomionego backendu.

---

## Podsumowanie bramek jakości

| Komenda | Cel | Wymagany Docker |
|---|---|---|
| `uv run pytest` | Backend: wszystkie testy integracyjne i jednostkowe | tak (testcontainers) |
| `uv run ruff check .` | Lint Python | nie |
| `cd frontend && npm test -- --run` | Frontend: vitest | nie |
| `cd frontend && npm run build` | Weryfikacja TypeScript + build | nie |
