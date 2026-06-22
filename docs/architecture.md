# Architektura systemu

## Warstwy

System zbudowany jest z kilku wyraźnie oddzielonych warstw:

```
┌─────────────────────────────────────────────────────────────────┐
│  Scrapery (Playwright)                                          │
│  otodom · nieruchomosci-online · hossa                          │
│  Protokół: Scraper · Rejestr: register()                        │
└────────────────────────────┬────────────────────────────────────┘
                             │ RawListing
┌────────────────────────────▼────────────────────────────────────┐
│  Normalizacja / IncrementalEngine                               │
│  raw_hash → pominięcie duplikatów → INSERT/UPDATE               │
└────────────────────────────┬────────────────────────────────────┘
                             │ Listing (PostgreSQL)
┌────────────────────────────▼────────────────────────────────────┐
│  Magazyn — PostgreSQL 18.4 + pgvector + PostGIS                 │
│  Source, Listing, PriceHistory, ScrapeRun                       │
│  LLMAnalysis, DedupGroup, DedupMember                          │
│  SavedSearch, Favorite, AppSetting                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  Wzbogacanie LLM                                                │
│  LLMClient (OpenAI-compat / FakeLLM)                            │
│  EnrichmentService — podsumowania, cechy, embeddingi            │
│  DedupService — grupy semantycznych duplikatów                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ pgvector embeddings
┌────────────────────────────▼────────────────────────────────────┐
│  Wyszukiwanie hybrydowe — SearchService                         │
│  1. Filtry SQL (city, district, price, area, rooms, market)     │
│  2. pgvector top-K (cosine similarity, zapytanie NL)            │
│  3. LLM rerank (opcjonalny)                                     │
│  Degradacja: bez LLM → filtry SQL + pgvector bez rerankowania  │
└────────────────────────────┬────────────────────────────────────┘
                             │ JSON
┌────────────────────────────▼────────────────────────────────────┐
│  API — FastAPI                                                  │
│  REST endpoints · SSE /events (EventBus)                        │
│  Scheduler (APScheduler, SCHEDULER_ENABLED)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│  Frontend — React 18 + Vite + TypeScript                        │
│  react-router v6 · typowany klient fetch · plain CSS            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Szczegóły kluczowych komponentów

### Scrapery

- Lokalizacja: `src/realestate/scrapers/`
- Protokół `Scraper` (structural subtyping / `typing.Protocol`): `source_id`, `display_name`, `build_search_url(criteria, page)`, `parse_search(html)`, `parse_detail(html, url)`.
- Wynik `parse_search` to lista obiektów `RawListing` (pydantic DTO).
- Rejestracja przez wywołanie `register(scraper)` na poziomie modułu.
- Istniejące wtyczki: `otodom` (parsuje `__NEXT_DATA__` JSON), `nieruchomosci-online` (DOM via selectolax), `hossa` (Vue SPA — wyniki to linki do kategorii inwestycji, nie pojedyncze oferty).
- Kontrakt pól per źródło: [`docs/scrapers-field-contract.md`](scrapers-field-contract.md).

### Normalizacja i IncrementalEngine

- Każda oferta otrzymuje `raw_hash` (hash kluczowych pól) → idempotentny zapis.
- `IncrementalEngine` synchronizuje wyniki scrape'u z bazą: nowe rekordy INSERT, zmiany ceny → PriceHistory, niezmienione → skip.
- Lokalizacja: `src/realestate/ingestion/`.

### Magazyn — PostgreSQL 18.4 + pgvector + PostGIS

- Schemat zarządzany przez Alembic (`migrations/`); aktualny head: `0009`.
- Kolumna `listings.embedding` — wektor pgvector. Wymiar kontrolowany przez jedyne źródło prawdy: `get_embedding_dim()` w `src/realestate/config.py` (domyślnie 1536). Wymiar **musi** być taki sam przy migracji i przy uruchomieniu aplikacji.
- Kolumna `listings.geom` — punkt PostGIS (`geometry(Point, 4326)`) synchronizowany triggerem z `lat/lon`; indeks GiST zasila agregacje mapowe.
- Endpoint `/listings/map/hexes` używa PostGIS (`ST_HexagonGrid`, `ST_Transform`, `ST_Intersects`, `ST_AsGeoJSON`) do budowania heksagonalnej heatmapy średnich cen i liczby ofert.
- Modele SQLAlchemy 2.0 async: `Source`, `Listing`, `PriceHistory`, `ScrapeRun`, `LLMAnalysis`, `DedupGroup`, `DedupMember`, `SavedSearch`, `Favorite`, `AppSetting`.
- Lokalizacja modeli: pakiet `src/realestate/models/` (pliki `base.py`, `listing.py`, `source.py`, `scrape_run.py`, `llm_analysis.py`, `dedup.py`, `user_data.py`); `Base` eksportowane z `realestate.models`.

### Wzbogacanie LLM

- `LLMClient` — klient OpenAI-compatible (domyślnie OpenRouter). Może być zastąpiony `FakeLLM` w testach.
- `EnrichmentService` — generuje podsumowania (`LLMAnalysis.summary`), cechy (`LLMAnalysis.features`), oblicza embeddingi i zapisuje je jako pgvector.
- `DedupService` — grupuje semantyczne duplikaty w tabeli `DedupGroup`/`DedupMember`.
- LLM jest wyłączony (degradacja) jeśli nie są ustawione: `LLM_API_KEY` + `LLM_MODEL` + `LLM_EMBEDDING_MODEL`.
- Lokalizacja: `src/realestate/enrichment/`, `src/realestate/llm/`.

### Wyszukiwanie hybrydowe — SearchService

Wyszukiwanie przebiega w trzech etapach:

1. **Filtry SQL** — zawężenie po mieście, dzielnicy, cenie, powierzchni, pokojach, typie rynku.
2. **pgvector top-K** — gdy podano zapytanie `q` (naturalny język), oblicza embedding zapytania i sortuje po podobieństwie cosinusowym.
3. **LLM rerank** — (opcjonalny) ponowne rangowanie top-K wyników przez LLM.

Degradacja: gdy LLM niedostępny, system pomija krok 3. Gdy brak embeddingów, pomija krok 2 i zwraca wyniki czysto przez SQL.

Lokalizacja: `src/realestate/search/`.

### API FastAPI

Endpointy:
- `GET /health` — health check
- `GET /listings` — lista z filtrami (city, district, min/max price/area/rooms, market, q, limit, offset) → `{items, total}`
- `GET /listings/{id}` — szczegóły + price_history + summary/features + duplicate_listing_ids
- `GET /stats` — statystyki ofert: overview, agregacje per dzielnica/źródło/miasto/rynek, pokoje i koszyki cenowe
- `GET /listings/map/points`, `GET /listings/map/hexes` — punkty i heksy mapy filtrowane po aktualnym viewport/bbox
- `POST /scrape`, `GET /scrape/runs`, `GET /scrape/runs/{id}` — zarządzanie scrape'ami
- `GET /events` — SSE: postęp scrape'u w czasie rzeczywistym
- `GET /searches`, `POST /searches`, `DELETE /searches/{id}` — zapisane wyszukiwania
- `GET /favorites`, `POST /favorites`, `DELETE /favorites/{listing_id}` — ulubione
- `GET /settings`, `PUT /settings` — konfiguracja aplikacji (klucz API nie jest nigdy zwracany)

Lokalizacja: `src/realestate/api/`.

### Scheduler

- APScheduler uruchamiany w lifespan FastAPI gdy `SCHEDULER_ENABLED=true`.
- Interwał domyślny: `SCHEDULER_DEFAULT_INTERVAL_MINUTES` (domyślnie 360).

### Frontend

- Lokalizacja: `frontend/` (samodzielny projekt pnpm).
- React 18 + Vite 8 + TypeScript 6 + react-router v6.
- Typowany klient fetch; plain CSS; Vitest 4 + Testing Library + MSW + jsdom 29.
- Lista ofert ma trzy widoki: domyślny grid, kompaktowy kafelek oraz pełnoszeroką listę z opisem i dodatkowymi szczegółami.
- Mapa ładuje punkty i heksy tylko dla widocznego viewportu (`north/south/east/west`), zamiast pobierać stały limit ofert z całego obszaru.
- Zmienna środowiskowa: `VITE_API_BASE` (domyślnie `http://localhost:8000`).
