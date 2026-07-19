## Why

Geocoding is best-effort today, but on any `httpx.HTTPError` (including Nominatim `429 Too Many Requests`) it logs a warning and returns `None` with **no retry** — so a transient rate-limit permanently drops the listing's coordinates. Since coordinates feed the map and the user wants them, transient geocoding failures must be retried with backoff.

## What Changes

- `NominatimGeocoder.geocode` retries transient errors (`429`, `401`, `403`, `5xx`, and transport errors) with the same exponential backoff already used by the scrapers (`scraper_max_retries`, `scraper_backoff_base_seconds`, `scraper_backoff_max_seconds`), honoring `Retry-After`.
- Permanent failures (non-retryable `4xx`, malformed payloads) are not retried and still return `None`.
- After exhausting retries, the failure is cached as `None` (unchanged behavior — a failed address is not re-hit within the process).

## Capabilities

### New Capabilities
- `geocoding-retry`: retry/backoff contract for geocoding HTTP and transport failures, sharing the scraper backoff settings.

### Modified Capabilities
- `scraping-ingestion`: extend the "Geocoding failures do not abort ingestion" requirement to add retry-with-backoff on transient geocoding errors.

## Impact

- `backend/src/realestate/ingestion/geocode.py` — retry loop in `geocode`.
- `backend/src/realestate/scrapers/helpers.py` — `_retry_after_seconds` moved here (shared with `browser.py`).
- Tests: `backend/tests/ingestion/test_geocode.py`.
- No API/DB/schema changes; behavior change only in failure-recovery path.
