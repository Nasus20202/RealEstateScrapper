## Why

`BrowserFetcher` retries only on HTTP `429`; every other block signal (e.g. the CloudFront `403` otodom returns) is caught by `is_blocked()` and immediately raised as `ScraperBlocked`, aborting the whole source scrape with no recovery. The remaining scrapers (`adresowo`, `morizon`, `nieruchomosci-online`, the developer sites) call `helpers.fetch_text`/`fetch_json` — a bare `urlopen` with **zero** retry/backoff, so any transient `403/5xx/timeout` throws and kills the run. We need a shared, config-driven backoff so transient blocks recover instead of failing silently.

## What Changes

- Extend `BrowserFetcher.fetch` to retry on a configurable set of retryable HTTP statuses (`403`, `429`, `5xx`) and on `is_blocked()`-detected pages, with exponential backoff honoring `Retry-After` and a max-attempt cap.
- Add the same retry/backoff behavior to `helpers.fetch_text` and `helpers.fetch_json` (the non-browser path used by most scrapers), so they no longer fail on transient HTTP errors.
- Add config knobs: `scraper_max_retries`, `scraper_backoff_base_seconds`, `scraper_backoff_max_seconds` (keep current `scraper_min_delay_seconds` throttle).
- Treat exhausted retries as `ScraperBlocked` (already classified as `blocked` in `ScrapeRun`), preserving existing error-isolation behavior.
- Backoff does **not** swallow permanent errors infinitely: capped attempts, then raise.

## Capabilities

### New Capabilities
- `fetcher-backoff`: shared retry/backoff contract for both browser and plain-HTTP fetch paths, covering retryable statuses, `Retry-After`, exponential growth, and attempt caps.

### Modified Capabilities
- `scraping-ingestion`: extend the "Browser Fetch Throttling and Block Detection" requirement to include retry/backoff on block signals and add a requirement covering plain-HTTP fetch resilience.

## Impact

- `backend/src/realestate/scrapers/browser.py` — retry loop + backoff in `fetch`.
- `backend/src/realestate/scrapers/helpers.py` — retry/backoff in `fetch_text`/`fetch_json`.
- `backend/src/realestate/config.py` — new backoff settings.
- Tests: `backend/tests/scrapers/test_browser.py`, `backend/tests/scrapers/test_helpers.py`.
- No API/DB/schema changes; behavior change only in failure-recovery path.
