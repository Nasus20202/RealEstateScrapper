## 1. Configuration

- [x] 1.1 Add `scraper_max_retries` (default `4`), `scraper_backoff_base_seconds` (default `1.0`), `scraper_backoff_max_seconds` (default `30.0`) to `backend/src/realestate/config.py` `Settings`.

## 2. Browser Fetcher Backoff

- [x] 2.1 Add a shared `_backoff_delay(attempt, retry_after, settings)` helper in `backend/src/realestate/scrapers/browser.py` computing `min(max, base * 2**attempt)` and honoring `Retry-After`.
- [x] 2.2 Extend `BrowserFetcher.fetch` retry loop to treat `403`, `401`, `429`, and `5xx` (plus `is_blocked()` pages) as retryable, using exponential backoff up to `scraper_max_retries`; raise `ScraperBlocked` when exhausted.
- [x] 2.3 Remove the now-redundant `_RATE_LIMIT_*` constants or fold them into the new settings-driven policy.

## 3. Plain-HTTP Fetch Resilience

- [x] 3.1 Add a `_retryable_status(status)` predicate and a `_http_retry` wrapper in `backend/src/realestate/scrapers/helpers.py`.
- [x] 3.2 Apply the wrapper to `fetch_text` and `fetch_json` so transient HTTP/transport errors retry with the same backoff policy; permanent client errors (`4xx` except `401`/`403`) propagate immediately.

## 4. Tests

- [x] 4.1 In `backend/tests/scrapers/test_browser.py`: update the `429` retry test to exponential expectations; add tests for `403`, `5xx`, `is_blocked()` retry, `Retry-After` honoring, and exhausted-retries → `ScraperBlocked`.
- [x] 4.2 Add `backend/tests/scrapers/test_helpers.py` covering `fetch_text`/`fetch_json` retry on transient errors, permanent `404` non-retry, and bounded attempts.

## 5. Validation

- [x] 5.1 Run `uv run ruff check .` and `uv run ruff format .` in `backend/`.
- [x] 5.2 Run `uv run pytest` in `backend/` and confirm new tests pass.
- [x] 5.3 Run `openspec validate --specs` from repo root.
