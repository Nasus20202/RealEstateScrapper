## Context

The backend registers scraper plugins via module import side-effect (`backend/src/realestate/scrapers/__init__.py`) and runs them through `run_search` in `backend/src/realestate/scrapers/runner.py`, which paginates, deduplicates by `(source_id, external_id)`, and optionally enriches search results with detail-page data. The default fetcher is `BrowserFetcher` (Playwright, headless Chromium), but the Trojmiasto.pl pages are server-rendered, so parsing the same DOM works for browser-fetched HTML and plain HTTP snapshots alike.

The target section is `https://ogloszenia.trojmiasto.pl/nieruchomosci-sprzedam-rynek-wtorny/` — "nieruchomości, sprzedam, rynek wtórny" (real estate for sale, secondary market), covering the Tricity region (~16k listings). Pagination is `?strona=N`. A sibling category `nieruchomosci-sprzedam-rynek-pierwotny` exists for primary market.

See proposal.md for motivation; specs/trojmiasto-scraper/spec.md for the behavior contract.

## Goals / Non-Goals

**Goals:**
- New `trojmiasto` scraper that reliably parses search and detail pages into `RawListing` using the existing selectolax DOM approach and shared helpers.
- Market (`secondary`/`primary`) derived from the scraped category, with `secondary` the default.
- Offline fixture-based tests plus browser-fetcher retry tests, and a field-contract doc entry.

**Non-Goals:**
- No new dependencies, DB schema, migrations, API routes, or frontend changes.
- No scraping of agent/agency contact details or map coordinates (coordinates are left to the existing best-effort geocoder).
- No support for other Trojmiasto.pl sections (rentals, other categories) or for search filtering translated to query params (consistent with other DOM scrapers; filtering is enforced downstream).

## Decisions

### 1. DOM parsing with selectolax + shared helpers
Reuse the pattern from `backend/src/realestate/scrapers/nieruchomosci_online.py` and the generic helpers in `backend/src/realestate/scrapers/helpers.py` (`clean_text`, `parse_money`, `parse_area`, `parse_rooms`, `parse_floor`, `absolute_url`, `image_url`, `looks_like_street_or_code`) plus `images.py` (`looks_like_listing_image`, `unique_listing_images`) for filtering/dedup of thumbnails.

- *Alternative considered:* scraping an embedded JSON blob. The pages embed only a JSON-LD `Product` block on the detail page, not on search pages, so a single JSON-driven approach does not work for both.

### 2. Stable `external_id` from `article[data-id]`
Listing cards carry `<article id="ogl-<id>" data-id="<id>">`. Use `data-id` as the numeric `external_id`; fall back to the `-ogl(\d+)\.html` pattern in the offer URL. This is stable across re-scrapes and is the deduplication key.

### 3. Concrete selectors
Verified against live HTML (search page and detail page):

- **Search cards:** `article.list__item[data-id]`
- **Title + URL:** `h2.list__item__content__title a.list__item__content__title__name`
- **Price:** `.list__item__price__value span`, fallback `.list__item__picture__price__currency`
- **Location text:** `p.list__item__content__subtitle`
- **Features:** `ul.list__item__details__icons li` matched by the `details--icons--element--powierzchnia` (area), `--l_pokoi` (rooms), `--pietro` (floor), `--rok_budowy` (year of construction) classes; value from `p.list__item__details__icons__element__desc`
- **Thumbnails:** `.list__item__picture img` via `image_url()` (handles lazy `data-src`); drop the `placeholder.svg` and `data:` sources before filtering
- **Detail title:** `h1.xogIndex__title`
- **Detail fields:** `.xogField--cena` (price), `.xogField--address` (address), `.xogField--powierzchnia` (area), `.xogField--l_pokoi` (rooms), `.xogField--pietro` (floor), `.xogField--rok_budowy` (year) — value from `.xogField__value`
- **Detail description + gallery:** JSON-LD block with `@type == "Product"` → `description` and ordered `image[]` array; fallback to `.lazy` images' `data-src`

### 4. Best-effort location decomposition
Subtitle formats observed: `"Gdańsk Zaspa Rozstaje"`, `"Gdańsk Śródmieście, Lawendowa"`, `"Puck, Kolejowa"`, `"Gdynia Chwarzno - Wiczlino, Stanisława Filipkowskiego"`. Implement a `_split_location(text)` helper: strip the leading known city (from a small Tricity-area city list, reuse `helpers.city_from_text`), split the remainder on `,`; leading words after the city → district, text after the first comma → street. Run the result through `looks_like_street_or_code` so postal codes / street names are never stored as `district`. Unit-test the helper with the formats above. Unknown cities degrade to `city=None`, leaving downstream geocoding to fall back gracefully.

### 5. Market from the canonical URL, not per-card
`parse_search(html)` has no URL, so read the page's `<link rel="canonical">` href: contains `-rynek-pierwotny` → `"primary"`, otherwise `"secondary"` (default, matching the target section). This avoids instance state and keeps market correct when `build_search_url` switches category for `criteria.market == "primary"`. The `Product` JSON-LD on detail pages has no market marker, so detail parsing leaves `market` unset and the runner's `_merge_detail`/`_with_search_context` preserves the search-level value.

### 6. Timestamp semantics
The site exposes only `<time datetime="YYYY-MM-DD HH:MM:SS">Zaktualizowano: …` (updated-at), not a true post date. Populate `posted_at` from this timestamp as a recency signal and document the caveat in the field contract. *Alternative considered:* leaving `posted_at` unset — rejected because the update time is the only freshness signal the portal provides and ingestion stores it unchanged.

### 7. Testing strategy
- **Offline unit tests** (`backend/tests/scrapers/test_trojmiasto_parser.py`) against gzipped fixtures in `backend/tests/fixtures/data/` (`trojmiasto_search.html.gz`, `trojmiasto_detail.html.gz`), following `test_nieruchomosci_online_parser.py`.
- **Browser-fetcher retry tests** (`backend/tests/scrapers/test_browser.py`): a transient navigation error is retried before returning the page, and repeated navigation errors raise `ScraperBlocked` after `scraper_max_retries`. No live/network test — fixtures pin parser behavior and avoid flaky external calls.

### 8. Retrying transient navigation failures in BrowserFetcher
Live probing showed the Trojmiasto.pl offer pages occasionally fail navigation with a transient error (`TimeoutError`, `net::ERR_NETWORK_CHANGED`). These surface as Playwright exceptions, not HTTP statuses, so `BrowserFetcher.fetch` previously propagated them immediately and aborted the whole scrape run (detail enrichment is part of the normal flow). `fetch` is extended so a navigation exception is treated like any other retryable outcome: exponential backoff between attempts, and a `ScraperBlocked` condition only after `scraper_max_retries` attempts. This mirrors the plain-HTTP helper (`helpers._fetch_bytes`), which already retries transport errors, and applies to all browser-fetched sources.

## Risks / Trade-offs

- **[Site markup changes]** → Mitigated by fixture-based tests that pin current selectors; the live test catches upstream drift on demand.
- **[Location decomposition imprecision]** → Best-effort by design; unknown components stay `None` and geocoding falls back to `Polska, {city}, {district}`. Documented as best-effort in the field contract.
- **[Market detection via canonical link]** → The canonical link is present on observed pages; if it ever disappears, the default (`secondary`) still matches the primary use case.
- **[Anti-bot/rate limiting / transient navigation errors]** → Handled by the existing `BrowserFetcher` throttling, backoff, and `ScraperBlocked` handling, extended so transient navigation failures (timeouts, network errors) are retried with backoff instead of aborting the run; no per-scraper logic needed.
- **[`posted_at` semantics]** → The field reflects "updated" not "posted"; explicitly documented so downstream consumers don't misread it as a publish date.

## Migration Plan

No schema or config migration. Adding the file under `backend/src/realestate/scrapers/` auto-registers the source via the plugin loader; existing scrape/settings/scheduler flows pick it up without changes. Rollback is removing the module, its tests, fixtures, the doc entry, and the `BrowserFetcher.fetch` retry extension.
