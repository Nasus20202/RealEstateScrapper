## Why

The listing catalog is missing a source for Trojmiasto.pl classifieds (`ogloszenia.trojmiasto.pl`), a major regional real-estate portal for Gdańsk, Gdynia, and Sopot with over 16,000 active secondary-market listings. Adding it increases catalog coverage and gives users a third aggregated portal (alongside Otodom and Nieruchomości-online) for Tricity secondary-market offers.

## What Changes

- Add a new scraper plugin `trojmiasto` (`source_id = "trojmiasto"`, `display_name = "Trojmiasto.pl"`) implementing the `Scraper` protocol in `backend/src/realestate/scrapers/trojmiasto.py`.
- `build_search_url` targets the `nieruchomosci-sprzedam-rynek-wtorny` category (secondary market) and honors `criteria.market == "primary"` by switching to the `nieruchomosci-sprzedam-rynek-pierwotny` category; defaults to secondary. Pagination uses the site's `?strona=N` parameter.
- `parse_search` extracts listings from `article.list__item[data-id]` cards: `external_id` (from `data-id`), URL, title, price, area, rooms, floor, year of construction, location text, thumbnail images, and the update timestamp.
- `parse_detail` enriches a listing from the offer page: full description (from the `Product` JSON-LD block), address, price/area/rooms/floor/year fields, and the gallery image list.
- Market is derived from the category (`secondary` for rynek-wtorny, `primary` for rynek-pierwotny) rather than guessed per-listing.
- Add offline fixture-based parser tests (no live/network test — fixtures pin the parser behavior) and document the per-source field contract in `docs/scrapers-field-contract.md`.
- Extend `BrowserFetcher` (`backend/src/realestate/scrapers/browser.py`) to retry transient navigation failures (navigation timeouts and network errors) with the existing exponential backoff, raising `ScraperBlocked` only after retries are exhausted. Live testing surfaced that these surface as exceptions, not HTTP statuses, so they previously aborted a run without retry; the plain-HTTP fetch helper already retries transport errors.
- No schema changes: the scraper reuses the existing `RawListing` DTO and registration/discovery mechanism (module import side effect), so no migration is needed.

## Capabilities

### New Capabilities
- `trojmiasto-scraper`: behavior contract for the Trojmiasto.pl scraper plugin — source identity, search URL construction (category + pagination), search/detail parsing rules, and the resulting `RawListing` field population.

### Modified Capabilities
- `scraping-ingestion`: the "Browser Fetch Throttling and Block Detection" requirement changes so that transient navigation failures are retried with exponential backoff and surface as blocked only after `scraper_max_retries` attempts.

## Impact

- **Code**: new `backend/src/realestate/scrapers/trojmiasto.py` (picked up automatically by the plugin loader in `scrapers/__init__.py`); new tests in `backend/tests/scrapers/`; new gzipped fixtures in `backend/tests/fixtures/data/`; `BrowserFetcher.fetch` retry extension plus tests in `tests/scrapers/test_browser.py`; documentation update in `docs/scrapers-field-contract.md`.
- **Runtime**: the source becomes selectable in scrape/settings/scheduler workflows via `source_id = "trojmiasto"`. Uses the existing browser fetcher (`BrowserFetcher`), throttling, and backoff; transient navigation failures are now retried before a run is marked blocked. No new dependencies.
- **API/database**: none — no routes, models, or migrations change.
- **Non-goals**: agent/agency contact info and map coordinates are not scraped (coordinates are left to the existing best-effort geocoder); no support for rentals or other category sections of the portal.
