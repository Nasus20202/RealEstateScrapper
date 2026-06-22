# Konfiguracja

Konfiguracja aplikacji odbywa się przez zmienne środowiskowe lub plik `.env` w katalogu głównym projektu (wzór: `.env.example`). Klasa `Settings` w `backend/src/realestate/config.py` używa `pydantic-settings` do walidacji i ładowania ustawień.

**Sekrety (np. `LLM_API_KEY`) nigdy nie powinny trafiać do repozytorium.** Używaj wyłącznie `.env` (lokalnie) lub zmiennych środowiskowych (CI/produkcja). `GET /settings` **nigdy** nie zwraca wartości `LLM_API_KEY` — zwraca tylko pole `llm_api_key_set` (boolean).

---

## Baza danych

| Zmienna         | Wymagana | Domyślna | Opis                                                                                                                                                     |
| --------------- | -------- | -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`  | **tak**  | —        | URL połączenia asyncpg, np. `postgresql+asyncpg://user:pass@localhost:5432/dbname`                                                                       |
| `EMBEDDING_DIM` | nie      | `2048`   | Wymiar wektora pgvector. **Musi być identyczny przy migracji i przy uruchomieniu aplikacji.** Jedyne źródło prawdy: `get_embedding_dim()` w `config.py`. |

> **Uwaga:** Alembic nie ładuje `.env`. Przed `alembic upgrade head` ustaw `EMBEDDING_DIM` jako prawdziwą zmienną środowiskową:
>
> ```bash
> EMBEDDING_DIM=2048 uv run alembic upgrade head
> ```

---

## Scraper

| Zmienna                     | Domyślna           | Opis                                                                 |
| --------------------------- | ------------------ | -------------------------------------------------------------------- |
| `SCRAPER_USER_AGENT`        | `Mozilla/5.0 …`    | User-Agent dla Playwright                                            |
| `SCRAPER_MIN_DELAY_SECONDS` | `1.5`              | Minimalne opóźnienie między żądaniami (sekundy)                      |
| `SCRAPER_NAV_TIMEOUT_MS`    | `30000`            | Timeout nawigacji Playwright (ms)                                    |
| `SCRAPER_WAIT_UNTIL`        | `domcontentloaded` | Warunek gotowości strony (`load`, `domcontentloaded`, `networkidle`) |

---

## Geokodowanie (mapa)

Dane ze scraperów nie zawierają współrzędnych, więc adres oferty (ulica/dzielnica/
miasto) jest geokodowany **przy ingestii** i zapisywany do kolumn `listings.lat`/
`listings.lon`. Dzięki temu oferty pojawiają się jako pinezki na mapie we frontendzie.
Domyślny dostawca to [OpenStreetMap Nominatim](https://nominatim.openstreetmap.org)
(darmowy, bez klucza API). Geokodowanie jest **best-effort** — błąd lub brak wyniku
nie przerywa scrapowania (oferta po prostu nie ma pinezki).

| Zmienna                       | Domyślna                                | Opis                                                                                           |
| ----------------------------- | --------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `GEOCODING_ENABLED`           | `true`                                  | Włącz geokodowanie adresów przy ingestii (`true`/`false`). Wyłączenie pomija pinezki na mapie. |
| `GEOCODING_BASE_URL`          | `https://nominatim.openstreetmap.org`   | URL bazowy usługi geokodującej (API zgodne z Nominatim).                                       |
| `GEOCODING_USER_AGENT`        | `RealEstateAggregator/1.0 (local tool)` | User-Agent wymagany przez politykę Nominatim.                                                  |
| `GEOCODING_MIN_DELAY_SECONDS` | `1.0`                                   | Minimalne opóźnienie między żądaniami (throttling — Nominatim wymaga ≤ 1 req/s).               |
| `GEOCODING_TIMEOUT_SECONDS`   | `10.0`                                  | Timeout pojedynczego żądania geokodowania (sekundy).                                           |

> **Uwaga:** wyniki są cache'owane w pamięci procesu wg adresu, więc ponowne
> scrapowanie tych samych ofert nie odpytuje usługi ponownie. Przy dużych wolumenach
> rozważ własną instancję Nominatim (`GEOCODING_BASE_URL`).

---

## LLM

Aplikacja korzysta z OpenAI-compatible API. Domyślny dostawca: [OpenRouter](https://openrouter.ai). LLM jest **wyłączony** (tryb degradacji) jeśli nie są ustawione **wszystkie trzy**: `LLM_API_KEY`, `LLM_MODEL`, `LLM_EMBEDDING_MODEL`.

| Zmienna               | Domyślna                       | Opis                                                                  |
| --------------------- | ------------------------------ | --------------------------------------------------------------------- |
| `LLM_BASE_URL`        | `https://openrouter.ai/api/v1` | URL bazowy API (OpenAI-compatible)                                    |
| `LLM_API_KEY`         | `None`                         | Klucz API (sekret — tylko `.env`, nigdy nie zwracany przez API)       |
| `LLM_MODEL`           | `None`                         | Model do generowania tekstu (np. `openai/gpt-4o-mini`)                |
| `LLM_EMBEDDING_MODEL` | `None`                         | Model do obliczania embeddingów (np. `openai/text-embedding-3-small`) |
| `LLM_TIMEOUT_SECONDS` | `30.0`                         | Timeout żądania do LLM (sekundy)                                      |
| `LLM_MAX_RETRIES`     | `2`                            | Liczba prób przy błędzie LLM                                          |

Gdy LLM jest wyłączony, system działa z degradacją:

- Brak podsumowań i cech (`LLMAnalysis`).
- Brak embeddingów → brak wyszukiwania semantycznego pgvector.
- Brak rerankowania wyników.
- Wyszukiwanie nadal działa przez filtry SQL.

---

## Scheduler (harmonogram)

Ustawienia scheduler (APScheduler):

| Zmienna                              | Domyślna | Opis                                                      |
| ------------------------------------ | -------- | --------------------------------------------------------- |
| `SCHEDULER_ENABLED`                  | `false`  | Włącz automatyczne cykliczne scrapowanie (`true`/`false`) |
| `SCHEDULER_DEFAULT_INTERVAL_MINUTES` | `360`    | Interwał między scrape'ami (minuty)                       |

Gdy `SCHEDULER_ENABLED=true`, APScheduler startuje w lifespan FastAPI.

---

## API / CORS

| Zmienna              | Domyślna | Opis                                                                                                                                                                      |
| -------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CORS_ALLOW_ORIGINS` | `*`      | Dozwolone originy CORS dla API (lista po przecinku albo `*`). Potrzebne, gdy frontend serwowany jest z innego originu niż API (np. `web` na `:8080` woła API na `:8000`). |

---

## Przykładowy plik `.env`

```dotenv
# Wymagane
DATABASE_URL=postgresql+asyncpg://realestate:realestate@localhost:5432/realestate

# Zalecane (musi zgadzać się z migracją)
EMBEDDING_DIM=2048

# LLM — opcjonalne, ale wymagane do wzbogacania i wyszukiwania semantycznego
LLM_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-4o-mini
LLM_EMBEDDING_MODEL=openai/text-embedding-3-small

# Scheduler — domyślnie wyłączony
# SCHEDULER_ENABLED=true
# SCHEDULER_DEFAULT_INTERVAL_MINUTES=360

# Geokodowanie — domyślnie włączone (Nominatim/OSM). Wyłącz, by pominąć pinezki.
# GEOCODING_ENABLED=false
```
