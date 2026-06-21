# Agregator ofert nieruchomości (Trójmiasto) — projekt

Data: 2026-06-21
Status: zaakceptowany projekt (przed planem implementacji)

## 1. Cel

Jedna lokalna aplikacja, która zbiera oferty mieszkań z wielu portali (Trójmiasto),
normalizuje je, przechowuje inkrementalnie, wzbogaca i dopasowuje przy pomocy LLM,
a następnie prezentuje w wygodnym interfejsie webowym z rankingiem dopasowania.

Zastępuje ręczne przeglądanie wielu serwisów (otodom.pl, nieruchomosci-online.pl,
rynekpierwotny.pl, morizon.pl, strony deweloperów jak hossa.gda.pl).

## 2. Zakres

### W zakresie (MVP)
- Architektura pluginowa scraperów + działające wtyczki dla **3 portali**:
  otodom.pl, nieruchomosci-online.pl oraz jeden deweloper (hossa.gda.pl).
- Inkrementalne pobieranie (tylko nowe/zmienione oferty), historia cen.
- Normalizacja do kanonicznego modelu oferty.
- Warstwa LLM (abstrakcja dostawcy, OpenRouter jako default): dopasowanie i ranking,
  podsumowania ofert, ekstrakcja cech, wykrywanie duplikatów, wyszukiwanie NL.
- PostgreSQL + pgvector do wyszukiwania hybrydowego (filtry + wektory + rerank LLM).
- Aplikacja webowa: backend FastAPI + frontend React/Vite.
- Ręczne odświeżanie z UI + harmonogram (APScheduler).
- Testy (TDD) i dokumentacja techniczna.

### Poza zakresem (na później)
- Pozostałe portale (rynekpierwotny.pl, morizon.pl, kolejni deweloperzy) — dokładane jako wtyczki.
- Powiadomienia (e-mail/push) o nowych ofertach.
- Mapa, eksport, multi-user/autoryzacja.
- Rozdzielenie na osobny worker/kolejkę (możliwe w przyszłości bez przepisywania logiki).

## 3. Decyzje (ustalone)

| Obszar | Decyzja |
|---|---|
| Interfejs | Lokalna aplikacja webowa |
| Stack | Python (FastAPI + Playwright) + React/Vite |
| Zakres portali | Fundament pluginowy + 3 portale w MVP |
| Rola LLM | Dopasowanie/ranking, podsumowania, dedup, wyszukiwanie NL |
| Dostawca LLM | W pełni konfigurowalny, OpenRouter jako default, **nic nie hardcodowane** |
| Kryteria | Twarde filtry + opis NL dla LLM |
| Odświeżanie | Ręcznie z UI + harmonogram |
| Magazyn | PostgreSQL + pgvector |
| Model wykonania | Modularny monolit (podejście A) |

## 4. Architektura

Modularny monolit: jeden proces FastAPI z wbudowanym schedulerem i asynchronicznymi
zadaniami w tle. Logika podzielona na warstwy z jasnymi interfejsami, tak aby w
przyszłości dało się wydzielić worker/kolejkę bez przepisywania rdzenia.

```
┌──────────────────────────────────────────────────────────────┐
│  Frontend (React + Vite)                                       │
│  lista ofert · twarde filtry · pole NL · ranking + uzasadnienie│
│  historia cen · duplikaty · ulubione · postęp scrapingu · ust. │
└───────────────▲────────────────────────────────────────────────┘
                │ REST + SSE
┌───────────────┴────────────────────────────────────────────────┐
│  API (FastAPI)                                                  │
│  /listings /scrape /searches /favorites /settings /events(SSE)  │
├─────────────────────────────────────────────────────────────────┤
│  Serwisy domenowe                                               │
│   • SearchService (filtry SQL → pgvector → rerank LLM)          │
│   • IngestionService (orkiestracja scrape → normalizacja → upsert)│
│   • IncrementalEngine (nowe/zmienione/usunięte, historia cen)   │
│   • EnrichmentService (LLM: summary, features, embeddings, dedup)│
│   • Scheduler (APScheduler) — okresowy i ręczny trigger          │
├─────────────────────────────────────────────────────────────────┤
│  Wtyczki scraperów (interfejs Scraper)                          │
│   otodom · nieruchomosci-online · hossa  (Playwright async)     │
├─────────────────────────────────────────────────────────────────┤
│  Abstrakcja LLM (OpenAI-compatible; base_url/key/model z konfig)│
│   chat (rank/summary/dedup/parse_query) · embeddings            │
├─────────────────────────────────────────────────────────────────┤
│  Magazyn: PostgreSQL + pgvector (SQLAlchemy async, Alembic)     │
└─────────────────────────────────────────────────────────────────┘
```

## 5. Komponenty i interfejsy

### 5.1 Wtyczka scrapera (`Scraper`)
Wspólny interfejs, jedna implementacja per portal, rejestr wtyczek do auto-odkrywania.

```python
class Scraper(Protocol):
    source_id: str           # np. "otodom"
    display_name: str

    async def search(self, criteria: SearchCriteria) -> AsyncIterator[RawListing]:
        """Iteruje po wynikach (paginacja) dla Trójmiasta; zwraca surowe oferty."""

    async def fetch_detail(self, url: str) -> RawListing:
        """Dociąga szczegóły pojedynczej oferty (gdy lista ma niepełne dane)."""
```

- Każda wtyczka odpowiada za własny parsing → zwraca `RawListing` (pola surowe + metadane źródła).
- Rate-limiting i retry z backoffem per wtyczka; konfigurowalne opóźnienia.
- Wykrycie blokady/anty-bota → wyjątek `ScraperBlocked` (log + sygnał do UI, bez wywracania całego przebiegu).
- Playwright: współdzielony, zarządzany kontekst przeglądarki; rozsądny user-agent, poszanowanie rate-limitów.

### 5.2 Normalizator
Mapuje `RawListing` (per portal) na kanoniczny `Listing`. Logika parsowania należy do wtyczki;
normalizator scala do wspólnego schematu i waliduje (Pydantic).

Kanoniczny `Listing` (pola kluczowe): `source`, `external_id`, `url`, `title`,
`price`, `price_per_m2`, `area_m2`, `rooms`, `floor`, `total_floors`, `city`,
`district`, `street?`, `lat?`, `lon?`, `market` (pierwotny/wtórny), `description`,
`images[]`, `posted_at?`, `raw_hash`, `first_seen`, `last_seen`, `status` (active/gone).

### 5.3 Magazyn (PostgreSQL + pgvector)
SQLAlchemy (async, asyncpg) + migracje Alembic. Rozszerzenie `pgvector`.

Tabele:
- `sources` — portale i ich konfiguracja/status.
- `listings` — kanoniczne oferty; unikalność `(source, external_id)`; `raw_hash` do wykrywania zmian; `embedding vector` (pgvector) dla wyszukiwania semantycznego.
- `price_history` — `(listing_id, price, observed_at)`.
- `scrape_runs` — przebiegi: czas, per-source statystyki (nowe/zmienione/usunięte/błędy).
- `llm_analysis` — wynik wzbogacenia per oferta, kluczowany hashem treści (cache).
- `dedup_groups` + `dedup_members` — grupy tej samej nieruchomości z różnych portali.
- `saved_searches` — twarde filtry + opis preferencji NL.
- `favorites` — oznaczone oferty.

### 5.4 Silnik inkrementalny
Porównuje świeży scrape ze stanem w bazie po `(source, external_id)` i `raw_hash`:
- nowa oferta → insert;
- zmieniony `raw_hash` → update + wpis do `price_history` przy zmianie ceny;
- brak w świeżym przebiegu (po N przebiegach) → `status = gone`.
Zapisuje statystyki do `scrape_runs`.

### 5.5 Warstwa LLM (abstrakcja dostawcy)
Interfejs niezależny od dostawcy; klient kompatybilny z OpenAI, `base_url` + `api_key`
+ `model` (chat) + `embedding_model` w konfiguracji (env/plik). Default: OpenRouter.
**Żaden dostawca/model nie jest zaszyty w kodzie.**

```python
class LLMClient(Protocol):
    async def complete(self, messages, *, response_format=None) -> LLMResult: ...
    async def embed(self, texts: list[str]) -> list[Vector]: ...
```

Funkcje domenowe (EnrichmentService / SearchService):
- `summarize(listing)` — zwięzłe streszczenie opisu.
- `extract_features(listing)` — cechy z nieustrukturyzowanego tekstu (balkon, stan, piętro…).
- `embed(listing)` — wektor do pgvector (opis + cechy).
- `match_and_rank(candidates, hard_filters, nl_preferences)` — wynik 0–100 + uzasadnienie.
- `find_duplicates(candidates)` — grupy duplikatów.
- `parse_nl_query(text)` — zamiana zapytania NL na filtry/strukturalne intencje.

Wszystkie wyniki cache'owane po hashu treści — brak ponownych wywołań dla
niezmienionych ofert (koszt + inkrementalność). Limity/koszty: konfigurowalny budżet
i batchowanie zapytań.

### 5.6 SearchService (wyszukiwanie hybrydowe)
1. **Twarde filtry** (SQL): cena, metraż, pokoje, piętro, dzielnica, rynek itd. — odsiewają zbiór.
2. **Podobieństwo wektorowe** (pgvector): embedding zapytania/preferencji NL → top-K kandydatów.
3. **Rerank LLM**: `match_and_rank` na kandydatach → finalny ranking + uzasadnienie.
Degradacja: brak LLM → ranking regułowy (np. cena/m², trafność filtrów).

### 5.7 API (FastAPI)
- `GET /listings` — filtry + ranking (paginacja).
- `POST /scrape` — ręczny trigger; `GET /scrape/runs`, `GET /scrape/runs/{id}` — status/statystyki.
- `GET/POST/PUT /searches` — zapisane wyszukiwania (filtry + opis NL).
- `GET/POST/DELETE /favorites`.
- `GET /listings/{id}` — szczegóły + historia cen + grupa duplikatów + analiza LLM.
- `GET/PUT /settings` — konfiguracja LLM/portali/harmonogramu.
- `GET /events` (SSE) — postęp scrapingu na żywo.

### 5.8 Scheduler
APScheduler w procesie: okresowy inkrementalny scrape wg interwału z konfiguracji.
Ręczny trigger z UI kolejkuje to samo zadanie (jedna ścieżka logiki, brak duplikacji).

### 5.9 Frontend (React + Vite)
- Lista ofert: twarde filtry (formularz) + pole opisu NL.
- Wyniki: karta oferty z wynikiem dopasowania, uzasadnieniem i podsumowaniem LLM, ceną/m².
- Szczegóły: galeria, historia cen (wykres), oznaczenie duplikatów (jedna nieruchomość, wiele źródeł).
- Ulubione; przycisk „Odśwież" z podglądem postępu (SSE).
- Ustawienia: dostawca/model LLM, portale, kryteria/harmonogram.

## 6. Przepływ danych

```
Ustaw kryteria (filtry + opis NL)
   → trigger (ręczny / harmonogram)
   → wtyczki pobierają oferty Trójmiasta (Playwright)
   → normalizacja do Listing (+ walidacja)
   → silnik inkrementalny: upsert + price_history
   → EnrichmentService (LLM): summary, features, embedding, dedup — cache po hashu
   → przy przeglądaniu: filtry SQL → pgvector top-K → rerank LLM
   → frontend: rankowane, odduplikowane, streszczone oferty
```

## 7. Obsługa błędów
- **Izolacja wtyczek:** awaria jednego portalu nie psuje przebiegu; statystyki per źródło.
- **Retry z backoffem** dla błędów przejściowych; `ScraperBlocked` → log + pominięcie + sygnał w UI.
- **LLM:** retry, degradacja do rankingu regułowego, limity kosztów.
- **Walidacja Pydantic:** wadliwe oferty logowane, niekrytyczne.
- **Migracje/baza:** zdrowotny check połączenia i rozszerzenia pgvector przy starcie.

## 8. Strategia testów (TDD)
- **Parsery/normalizatory:** testy na zapisanych fixture'ach HTML (raz nagrane realne strony,
  parsowanie offline — szybkie, deterministyczne, bez sieci).
- **Scrapery:** integracyjne na fixture'ach; opcjonalne „smoke" testy na żywo (oznaczone, poza CI).
- **Warstwa LLM:** fake provider implementujący interfejs (deterministyczny) + cache'owane odpowiedzi jako fixture.
- **Silnik inkrementalny:** nowe/zmienione/usunięte/zmiana ceny.
- **SearchService:** filtry + ścieżka wektorowa (na testowej bazie pgvector) + degradacja bez LLM.
- **API:** FastAPI TestClient.
- **Frontend:** Vitest (komponenty) + e2e Playwright dla samej aplikacji.
- **Baza w testach:** PostgreSQL+pgvector w kontenerze (np. testcontainers / docker-compose test).

## 9. Konfiguracja
- Plik `.env` / `settings` (Pydantic Settings): połączenie DB, dostawca LLM (`base_url`,
  `api_key`, `model`, `embedding_model`), interwał harmonogramu, rate-limity per portal,
  budżet LLM. Brak sekretów w repo (`.env.example` jako wzór).

## 10. Repo / inicjalizacja
- `AGENTS.md` + symlink `CLAUDE.md → AGENTS.md` (instrukcje dla agentów/dev).
- Specyfikacje: `docs/superpowers/specs/`.
- Dokumentacja techniczna: `docs/` (architektura, uruchomienie, dodawanie wtyczki, konfiguracja LLM).
- `docker-compose.yml`: PostgreSQL + pgvector (i opcjonalnie aplikacja).
- **speckit/openspec: pominięte** — dublują się z procesem spec→plan (superpowers). Do dołożenia tylko na życzenie.

## 11. Uwaga prawna / etyczna
Scraping bywa sprzeczny z regulaminami portali. Rozwiązanie projektowane do użytku
osobistego, z poszanowaniem rate-limitów i robots. Zaznaczone w dokumentacji; użytkownik
odpowiada za zgodność z ToS portali.

## 12. Kryteria sukcesu (MVP)
- Jedna komenda uruchamia bazę + aplikację lokalnie.
- Inkrementalny scrape z 3 portali zapełnia bazę, z historią cen i statystykami przebiegu.
- Wyszukiwanie hybrydowe zwraca rankowane, odduplikowane oferty z uzasadnieniem i podsumowaniem.
- Ręczne odświeżanie z UI i harmonogram działają, postęp widoczny na żywo.
- Komplet testów przechodzi; dokumentacja techniczna kompletna.
