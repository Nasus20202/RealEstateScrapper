## 1. Fixtures and Offline Tests (TDD)

- [x] 1.1 Capture gzipped HTML fixtures from the live site into `backend/tests/fixtures/data/`: `trojmiasto_search.html.gz` (search page with `article.list__item` cards) and `trojmiasto_detail.html.gz` (a matching detail page)
- [x] 1.2 Write `backend/tests/scrapers/test_trojmiasto_parser.py` (offline, no network): `parse_search` returns `>= 1` listing with correct `source_id`/`external_id`/absolute `url`/`title`; price/area/rooms/floor present on at least one card; images are absolute; `market == "secondary"` from the search fixture
- [x] 1.3 Add offline tests for `build_search_url`: page 1 has no `strona` param; page 2 appends `?strona=2`; `criteria.market == "primary"` selects `nieruchomosci-sprzedam-rynek-pierwotny`; default is `nieruchomosci-sprzedam-rynek-wtorny`
- [x] 1.4 Add offline tests for `parse_detail` against the detail fixture: non-empty title, description from the `Product` JSON-LD, gallery image URLs absolute and de-duplicated, address/price/area/rooms/floor/year parsed
- [x] 1.5 Add unit tests for `_split_location` covering `"Gdańsk Zaspa Rozstaje"`, `"Gdańsk Śródmieście, Lawendowa"`, `"Puck, Kolejowa"`, `"Gdynia Chwarzno - Wiczlino, Stanisława Filipkowskiego"`, and a postal-code case that must not land in `district`
- [x] 1.6 Run `uv run pytest tests/scrapers/test_trojmiasto_parser.py` and confirm the new tests fail (module does not exist yet)

## 2. Implement the Scraper Plugin

- [x] 2.1 Implement `backend/src/realestate/scrapers/trojmiasto.py` with `TrojmiastoScraper` (`source_id = "trojmiasto"`, `display_name = "Trojmiasto.pl"`) implementing `build_search_url`, `parse_search`, and `parse_detail` per design.md, registering via module-level `register(...)`
- [x] 2.2 Confirm auto-discovery: importing `realestate.scrapers` populates the registry with the `trojmiasto` source (verify with a quick REPL check or the offline tests that import the module)
- [x] 2.3 Run `uv run pytest tests/scrapers/test_trojmiasto_parser.py` until all offline parser tests pass

## 3. Field Contract Documentation

- [x] 3.1 Add a `trojmiasto` (`source_id = "trojmiasto"`) section to `docs/scrapers-field-contract.md` listing search-level field availability, the `market` derivation rule, and the timestamp semantics (updated-at, not posted-at)

## 4. Browser Fetcher: Retry Transient Navigation Failures

- [x] 4.1 Extend `BrowserFetcher.fetch` in `backend/src/realestate/scrapers/browser.py` so that transient navigation failures (navigation timeout, network errors) are retried with the existing exponential backoff instead of aborting the run, raising `ScraperBlocked` only after `scraper_max_retries` attempts
- [x] 4.2 Add offline tests in `backend/tests/scrapers/test_browser.py`: a transient navigation error is retried before returning the page, and repeated navigation errors raise `ScraperBlocked` after retries are exhausted
- [x] 4.3 Remove the live end-to-end test (decision: not needed; offline fixtures pin the parser behavior)
- [x] 4.4 Run `uv run pytest tests/scrapers/test_browser.py tests/scrapers/test_trojmiasto_parser.py` and confirm all pass

## 5. Validation and Commit

- [x] 5.1 Run `uv run ruff check .` and `uv run ruff format .` from `backend/` and fix any violations
- [x] 5.2 Run the full backend suite `uv run pytest` and confirm it passes
- [x] 5.3 Run `openspec validate --changes` from the repo root and confirm the change is valid
- [x] 5.4 Commit the scraper, fixtures, tests, doc entry, browser-fetch fix, and OpenSpec change artifacts
